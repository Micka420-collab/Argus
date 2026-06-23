"""
Service d'enrichissement — AbuseIPDB + VirusTotal
Enrichit les IPs malveillantes avec des données de threat intel.
"""
import asyncio
import logging
from typing import Optional

import httpx
import redis.asyncio as redis

from api.core.config import settings
from api.core.http import get_http_client
from api.services.opensearch import OpenSearchClient
from api.services.scoring import compute_risk_score

logger = logging.getLogger(__name__)

# Cache Redis pour les enrichissements
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=False,
        )
    return _redis_client


class EnrichmentService:
    """Enrichit les IOCs (IP, hash) depuis des sources externes."""

    async def enrich_ip(self, ip: str, alert_id: str):
        """
        Enrichit une IP en parallèle depuis AbuseIPDB et VirusTotal.
        Résultat mis en cache Redis + mis à jour dans OpenSearch.
        """
        # Vérifier le cache Redis d'abord
        cached = await self._get_cached(ip)
        if cached:
            logger.debug("Enrichissement IP %s depuis cache", ip)
            await self._update_alert(alert_id, cached)
            return

        # Requêtes parallèles
        results = await asyncio.gather(
            self._abuseipdb(ip),
            self._virustotal_ip(ip),
            return_exceptions=True,
        )

        enrichment = {
            "ip": ip,
            "abuseipdb":  results[0] if not isinstance(results[0], Exception) else None,
            "virustotal": results[1] if not isinstance(results[1], Exception) else None,
        }

        # Score de risque agrégé (scorer unifié — identique à l'investigation OSINT)
        assessment = compute_risk_score(enrichment)
        enrichment["risk_score"] = assessment.score
        enrichment["verdict"]    = assessment.verdict
        enrichment["confidence"] = assessment.confidence

        # Mise en cache
        await self._cache_result(ip, enrichment)

        # Mise à jour alerte dans OpenSearch
        await self._update_alert(alert_id, enrichment)

        # Escalade si IP très malveillante
        if enrichment["risk_score"] >= settings.ENRICH_RISK_THRESHOLD:
            logger.warning(
                "IP hautement malveillante détectée: %s (score=%d)",
                ip, enrichment["risk_score"],
            )
            await self._auto_escalate(ip, alert_id, enrichment)

    # ----------------------------------------------------------
    # AbuseIPDB
    # https://docs.abuseipdb.com
    # ----------------------------------------------------------
    async def _abuseipdb(self, ip: str) -> Optional[dict]:
        if not settings.ABUSEIPDB_KEY:
            return None

        headers = {"Key": settings.ABUSEIPDB_KEY, "Accept": "application/json"}
        params = {"ipAddress": ip, "maxAgeInDays": 90, "verbose": True}

        async with get_http_client(timeout=10) as client:
            r = await client.get(
                "https://api.abuseipdb.com/api/v2/check",
                headers=headers,
                params=params,
            )
            r.raise_for_status()
            data = r.json()["data"]
            return {
                "abuse_score":    data["abuseConfidenceScore"],
                "country":        data["countryCode"],
                "isp":            data.get("isp", ""),
                "domain":         data.get("domain", ""),
                "reports":        data["totalReports"],
                "last_reported":  data.get("lastReportedAt", ""),
                "is_tor":         data.get("isTor", False),
                "is_public":      data.get("isPublic", True),
                "usage_type":     data.get("usageType", ""),
            }

    # ----------------------------------------------------------
    # VirusTotal
    # https://developers.virustotal.com/reference/ip-object
    # ----------------------------------------------------------
    async def _virustotal_ip(self, ip: str) -> Optional[dict]:
        if not settings.VIRUSTOTAL_KEY:
            return None

        headers = {"x-apikey": settings.VIRUSTOTAL_KEY}
        async with get_http_client(timeout=10) as client:
            r = await client.get(
                f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
                headers=headers,
            )
            if r.status_code == 404:
                return {"malicious": 0, "suspicious": 0, "harmless": 0, "undetected": 0}
            r.raise_for_status()
            attrs = r.json()["data"]["attributes"]
            stats = attrs.get("last_analysis_stats", {})
            return {
                "malicious":  stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "harmless":   stats.get("harmless", 0),
                "undetected": stats.get("undetected", 0),
                "as_owner":   attrs.get("as_owner", ""),
                "country":    attrs.get("country", ""),
                "reputation": attrs.get("reputation", 0),
                "network":    attrs.get("network", ""),
            }

    async def enrich_hash(self, file_hash: str, alert_id: str):
        """Enrichit un hash de fichier via VirusTotal."""
        if not settings.VIRUSTOTAL_KEY:
            return

        headers = {"x-apikey": settings.VIRUSTOTAL_KEY}
        async with get_http_client(timeout=15) as client:
            try:
                r = await client.get(
                    f"https://www.virustotal.com/api/v3/files/{file_hash}",
                    headers=headers,
                )
                if r.status_code == 404:
                    return
                r.raise_for_status()
                attrs = r.json()["data"]["attributes"]
                stats = attrs.get("last_analysis_stats", {})
                enrichment = {
                    "hash":        file_hash,
                    "malicious":   stats.get("malicious", 0),
                    "suspicious":  stats.get("suspicious", 0),
                    "file_name":   attrs.get("meaningful_name", ""),
                    "file_type":   attrs.get("type_description", ""),
                    "size":        attrs.get("size", 0),
                    "first_seen":  attrs.get("first_submission_date", ""),
                }
                await self._update_alert(alert_id, {"enrichment_hash": enrichment})
            except Exception as e:
                logger.error("Erreur enrichissement hash %s: %s", file_hash, e)

    # ----------------------------------------------------------
    # Score de risque agrégé
    # ----------------------------------------------------------
    def _compute_risk(self, enrichment: dict) -> int:
        """Score 0-100 — délègue au scorer unifié (services.scoring)."""
        return compute_risk_score(enrichment).score

    # ----------------------------------------------------------
    # Cache et persistence
    # ----------------------------------------------------------
    async def _get_cached(self, ip: str) -> Optional[dict]:
        try:
            import json
            r = await get_redis()
            raw = await r.get(f"enrich:{ip}")
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    async def _cache_result(self, ip: str, enrichment: dict):
        try:
            import json
            r = await get_redis()
            await r.setex(
                f"enrich:{ip}",
                settings.ENRICH_CACHE_TTL,
                json.dumps(enrichment),
            )
        except Exception as e:
            logger.warning("Erreur cache Redis: %s", e)

    async def _update_alert(self, alert_id: str, enrichment: dict):
        try:
            os = OpenSearchClient()
            await os.update_alert(alert_id, {"enrichment": enrichment})
        except Exception as e:
            logger.error("Erreur mise à jour alerte OpenSearch: %s", e)

    async def _auto_escalate(self, ip: str, alert_id: str, enrichment: dict):
        """Escalade automatique pour IP très malveillante."""
        from api.services.notifications import NotificationService
        notif = NotificationService()
        score = enrichment.get("risk_score", 0)
        abuse = enrichment.get("abuseipdb", {})
        await notif.send_all(
            f"⚠️ ESCALADE — IP hautement malveillante\n"
            f"IP: {ip}\n"
            f"Score risque: {score}/100\n"
            f"Abuse reports: {abuse.get('reports', 0)}\n"
            f"ISP: {abuse.get('isp', 'N/A')}\n"
            f"Pays: {abuse.get('country', 'N/A')}\n"
            f"Alerte ID: {alert_id}",
            priority="critical",
        )


async def cleanup_old_enrichments():
    """Tâche planifiée — Redis gère le TTL automatiquement."""
    try:
        r = await get_redis()
        info = await r.info("stats")
        expired = info.get("expired_keys", 0)
        logger.info("Redis — clés expirées: %s", expired)
    except Exception as e:
        logger.error("Erreur cleanup_old_enrichments: %s", e)
