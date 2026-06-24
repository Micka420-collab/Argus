"""
SOC Platform — Service d'Investigation OSINT
Répond à la question : QUI attaque notre infrastructure ?

Sources parallèles :
  - ip-api.com          → Géolocalisation + ISP + ASN + proxy/VPN/hosting (gratuit)
  - AbuseIPDB           → Score confiance + historique signalements communautaires
  - VirusTotal          → Détection moteurs antivirus / réputation
  - RDAP (ARIN/RIPE)    → WHOIS enrichi (registrar, AS owner, contact abus)
  - PTR/rDNS            → Reverse DNS
  - OpenSearch interne  → Toutes NOS alertes liées à cette IP
  - Classification      → Type d'attaque déduit (DDoS, bruteforce, scan, exploit…)
  - Risk assessment     → Score 0-100 + actions recommandées

Cache :
  - Redis TTL 1 heure pour AbuseIPDB + VirusTotal (quotas API gratuits limités)
  - Redis TTL 24 heures pour géolocalisation (données quasi-statiques)
"""

import asyncio
import json
import socket
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import redis.asyncio as aioredis
from pydantic import BaseModel

from api.core.config import settings
from api.core.http import get_http_client
from api.services.opensearch import OpenSearchClient
from api.services.scoring import (
    Evidence,
    RecommendedAction,
    RiskAssessment,
    compute_verdict,
)
from api.services.llm import AiAnalysis, analyze as llm_analyze

# ---------------------------------------------------------------------------
# Client Redis partagé (initialisé au premier appel)
# ---------------------------------------------------------------------------
_redis_client: aioredis.Redis | None = None

async def _get_redis() -> aioredis.Redis | None:
    """Retourne le client Redis, ou None si Redis est indisponible."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await _redis_client.ping()
        except Exception as e:
            logger.warning("Redis indisponible pour le cache investigation: %s", e)
            _redis_client = None
    return _redis_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mapping catégories AbuseIPDB (IDs → libellés)
# ---------------------------------------------------------------------------
ABUSE_CATEGORIES: dict[int, str] = {
    1: "DNS Compromise",     2: "DNS Poisoning",      3: "Fraud Orders",
    4: "DDoS Attack",        5: "FTP Brute-Force",    6: "Ping of Death",
    7: "Phishing",           8: "Fraud VoIP",         9: "Open Proxy",
    10: "Web Spam",          11: "Email Spam",         12: "Blog Spam",
    13: "VPN IP",            14: "Port Scan",          15: "Hacking",
    16: "SQL Injection",     17: "Spoofing",           18: "Brute-Force",
    19: "Bad Web Bot",       20: "Exploited Host",     21: "Web App Attack",
    22: "SSH Brute-Force",   23: "IoT Targeted",
}

# ---------------------------------------------------------------------------
# Modèles Pydantic des résultats
# ---------------------------------------------------------------------------

class IpGeoInfo(BaseModel):
    ip:            str
    country:       str  = ""
    country_code:  str  = ""
    region:        str  = ""
    city:          str  = ""
    lat:           float = 0.0
    lon:           float = 0.0
    timezone:      str  = ""
    isp:           str  = ""
    org:           str  = ""
    asn:           str  = ""
    asn_name:      str  = ""
    is_proxy:      bool = False
    is_hosting:    bool = False
    is_mobile:     bool = False
    reverse_dns:   str  = ""


class AbuseReport(BaseModel):
    confidence_score: int        = 0
    total_reports:    int        = 0
    last_reported:    str        = ""
    usage_type:       str        = ""
    domain:           str        = ""
    isp:              str        = ""
    categories:       list[str]  = []
    recent_comments:  list[str]  = []


class VirusTotalReport(BaseModel):
    malicious:          int       = 0
    suspicious:         int       = 0
    harmless:           int       = 0
    undetected:         int       = 0
    last_analysis_date: str       = ""
    reputation:         int       = 0
    tags:               list[str] = []


class AttackProfile(BaseModel):
    type:                str        = "unknown"   # ddos|bruteforce|portscan|exploit|webattack
    sub_type:            str        = ""
    intensity:           str        = "low"       # low|medium|high|critical
    first_seen:          str        = ""
    last_seen:           str        = ""
    alert_count:         int        = 0
    targeted_services:   list[str]  = []
    top_rules:           list[dict] = []
    requests_per_minute: float      = 0.0


# RecommendedAction & RiskAssessment sont désormais définis dans services.scoring
# (source de vérité unique) et importés ci-dessus.


class InvestigationReport(BaseModel):
    ip:             str
    timestamp:      str
    geo:            IpGeoInfo
    abuse:          AbuseReport
    virustotal:     VirusTotalReport
    attack_profile: AttackProfile
    risk:           RiskAssessment
    ai:             AiAnalysis | None = None
    raw_rdap:       dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------

class InvestigationService:
    """
    Orchestre une investigation OSINT complète sur une IP suspecte.
    Toutes les sources sont interrogées en parallèle (asyncio.gather).
    """

    def __init__(self):
        self._os = OpenSearchClient()

    # ------------------------------------------------------------------
    # Helpers cache Redis
    # ------------------------------------------------------------------
    async def _cache_get(self, key: str) -> dict | None:
        r = await _get_redis()
        if not r:
            return None
        try:
            raw = await r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def _cache_set(self, key: str, value: dict, ttl: int) -> None:
        r = await _get_redis()
        if not r:
            return
        try:
            await r.setex(key, ttl, json.dumps(value))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Point d'entrée public
    # ------------------------------------------------------------------
    async def investigate(
        self, ip: str, refresh: bool = False, with_ai: bool = True
    ) -> InvestigationReport:
        """
        Investigation OSINT complète sur une IP.

        with_ai=False : ne PAS appeler le LLM pour rédiger le récit (et ne pas
        mettre en cache le rapport partiel). Utilisé par l'agent autonome, qui
        rédige lui-même un récit enrichi — évite un DOUBLE appel LLM coûteux.
        """
        logger.info("Investigation OSINT démarrée pour l'IP : %s (refresh=%s, ai=%s)",
                    ip, refresh, with_ai)

        # Vérifier le cache Redis pour un rapport complet (TTL 1 heure)
        cache_key = f"investigation:{ip}"
        if not refresh:
            cached = await self._cache_get(cache_key)
            if cached:
                logger.info("Investigation récupérée depuis le cache Redis pour %s", ip)
                try:
                    return InvestigationReport(**cached)
                except Exception:
                    logger.info("Cache obsolète pour %s — ré-investigation", ip)

        geo_t, abuse_t, vt_t, rdap_t, hist_t, ptr_t = await asyncio.gather(
            self._fetch_geo(ip),
            self._fetch_abuseipdb(ip),
            self._fetch_virustotal(ip),
            self._fetch_rdap(ip),
            self._fetch_attack_history(ip),
            self._resolve_ptr(ip),
            return_exceptions=True,
        )

        # Substituer les exceptions par des valeurs vides
        geo      = geo_t      if isinstance(geo_t,  IpGeoInfo) else IpGeoInfo(ip=ip)
        abuse_raw = abuse_t   if isinstance(abuse_t, dict)   else {}
        vt_raw   = vt_t       if isinstance(vt_t,   dict)    else {}
        rdap     = rdap_t     if isinstance(rdap_t,  dict)   else {}
        history  = hist_t     if isinstance(hist_t,  list)   else []
        ptr      = ptr_t      if isinstance(ptr_t,   str)    else ""

        geo.reverse_dns = ptr

        abuse   = self._parse_abuseipdb(abuse_raw)
        vt      = self._parse_virustotal(vt_raw)
        profile = self._build_attack_profile(history, abuse)
        risk    = self._assess_risk(abuse, vt, profile, geo)
        ai      = await self._ai_analyze(ip, geo, abuse, vt, profile, risk) if with_ai else None

        report = InvestigationReport(
            ip=ip,
            timestamp=datetime.now(timezone.utc).isoformat(),
            geo=geo,
            abuse=abuse,
            virustotal=vt,
            attack_profile=profile,
            risk=risk,
            ai=ai,
            raw_rdap=rdap,
        )

        # Ne mettre en cache que le rapport COMPLET (avec récit IA) pour ne pas
        # polluer le cache OSINT consommé par la page Investigation.
        if with_ai:
            await self._cache_set(cache_key, report.model_dump(), ttl=3600)
        return report

    # ------------------------------------------------------------------
    # Géolocalisation + ISP  (ip-api.com — gratuit, 45 req/min)
    # ------------------------------------------------------------------
    async def _fetch_geo(self, ip: str) -> IpGeoInfo:
        fields = (
            "status,continent,country,countryCode,region,city,"
            "lat,lon,timezone,isp,org,as,asname,reverse,proxy,hosting,mobile,query"
        )
        try:
            # ip-api.com (offre gratuite = HTTP). Routé via get_http_client pour
            # bénéficier de l'égress anonymisé (Tor) si OSINT_ANON est actif.
            async with get_http_client(timeout=6) as client:
                r = await client.get(
                    f"http://ip-api.com/json/{ip}",
                    params={"fields": fields},
                )
                data = r.json()
        except Exception as e:
            logger.warning("ip-api.com indisponible: %s", e)
            return IpGeoInfo(ip=ip)

        if data.get("status") != "success":
            return IpGeoInfo(ip=ip)

        asn_raw  = data.get("as", "")          # ex: "AS3215 Orange S.A."
        asn_num  = asn_raw.split(" ")[0] if asn_raw else ""
        asn_name = " ".join(asn_raw.split(" ")[1:]) if asn_raw else ""

        return IpGeoInfo(
            ip=ip,
            country=data.get("country", ""),
            country_code=data.get("countryCode", "").lower(),
            region=data.get("region", ""),
            city=data.get("city", ""),
            lat=float(data.get("lat", 0)),
            lon=float(data.get("lon", 0)),
            timezone=data.get("timezone", ""),
            isp=data.get("isp", ""),
            org=data.get("org", ""),
            asn=asn_num,
            asn_name=asn_name,
            is_proxy=bool(data.get("proxy", False)),
            is_hosting=bool(data.get("hosting", False)),
            is_mobile=bool(data.get("mobile", False)),
        )

    # ------------------------------------------------------------------
    # AbuseIPDB — rapport verbeux (90 derniers jours)
    # ------------------------------------------------------------------
    async def _fetch_abuseipdb(self, ip: str) -> dict:
        if not settings.ABUSEIPDB_KEY:
            return {}
        try:
            async with get_http_client(timeout=8) as client:
                r = await client.get(
                    "https://api.abuseipdb.com/api/v2/check",
                    params={
                        "ipAddress":    ip,
                        "maxAgeInDays": 90,
                        "verbose":      True,
                    },
                    headers={
                        "Key":    settings.ABUSEIPDB_KEY,
                        "Accept": "application/json",
                    },
                )
                return r.json().get("data", {})
        except Exception as e:
            logger.warning("AbuseIPDB indisponible: %s", e)
            return {}

    def _parse_abuseipdb(self, data: dict) -> AbuseReport:
        if not data:
            return AbuseReport()

        reports     = data.get("reports", [])
        all_cat_ids: set[int] = set()
        for rep in reports[:50]:
            all_cat_ids.update(rep.get("categories", []))
        categories = [ABUSE_CATEGORIES.get(c, f"Cat.{c}") for c in all_cat_ids]

        comments = [
            rep.get("comment", "")[:200]
            for rep in reports[:5]
            if rep.get("comment")
        ]

        return AbuseReport(
            confidence_score=data.get("abuseConfidenceScore", 0),
            total_reports=data.get("totalReports", 0),
            last_reported=data.get("lastReportedAt", "") or "",
            usage_type=data.get("usageType", "") or "",
            domain=data.get("domain", "") or "",
            isp=data.get("isp", "") or "",
            categories=categories[:12],
            recent_comments=comments,
        )

    # ------------------------------------------------------------------
    # VirusTotal — IP report
    # ------------------------------------------------------------------
    async def _fetch_virustotal(self, ip: str) -> dict:
        if not settings.VIRUSTOTAL_KEY:
            return {}
        try:
            async with get_http_client(timeout=8) as client:
                r = await client.get(
                    f"https://www.virustotal.com/api/v3/ip_addresses/{ip}",
                    headers={"x-apikey": settings.VIRUSTOTAL_KEY},
                )
                if r.status_code != 200:
                    return {}
                return r.json().get("data", {}).get("attributes", {})
        except Exception as e:
            logger.warning("VirusTotal indisponible: %s", e)
            return {}

    def _parse_virustotal(self, data: dict) -> VirusTotalReport:
        if not data:
            return VirusTotalReport()
        stats = data.get("last_analysis_stats", {})
        ts    = data.get("last_analysis_date", 0)
        date_str = ""
        if ts:
            try:
                date_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except Exception:
                pass
        return VirusTotalReport(
            malicious=stats.get("malicious", 0),
            suspicious=stats.get("suspicious", 0),
            harmless=stats.get("harmless", 0),
            undetected=stats.get("undetected", 0),
            last_analysis_date=date_str,
            reputation=data.get("reputation", 0),
            tags=data.get("tags", [])[:10],
        )

    # ------------------------------------------------------------------
    # RDAP / WHOIS (ARIN → RIPE fallback)
    # ------------------------------------------------------------------
    async def _fetch_rdap(self, ip: str) -> dict:
        urls = [
            f"https://rdap.arin.net/registry/ip/{ip}",
            f"https://rdap.db.ripe.net/ip/{ip}",
            f"https://rdap.apnic.net/ip/{ip}",
        ]
        async with get_http_client(timeout=8) as client:
            for url in urls:
                try:
                    r = await client.get(url)
                    if r.status_code == 200:
                        return r.json()
                except Exception:
                    continue
        return {}

    # ------------------------------------------------------------------
    # PTR / Reverse DNS
    # ------------------------------------------------------------------
    async def _resolve_ptr(self, ip: str) -> str:
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
            return result[0]
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Historique interne — toutes nos alertes liées à cette IP
    # ------------------------------------------------------------------
    async def _fetch_attack_history(self, ip: str) -> list[dict]:
        try:
            client = await self._os.get_client()
            body = {
                "size": 500,
                "sort": [{"@timestamp": {"order": "desc"}}],
                "query": {
                    "bool": {
                        "should": [
                            {"term": {"data.srcip":     ip}},
                            {"term": {"data.src_ip":    ip}},
                            {"term": {"src_ip":         ip}},
                            {"term": {"data.win.system.ipAddress": ip}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "_source": [
                    "@timestamp",
                    "rule.id", "rule.description", "rule.level", "rule.mitre",
                    "agent.name", "agent.ip",
                    "data.dstport", "data.srcport", "data.proto",
                ],
            }
            resp = await client.search(index="wazuh-alerts-*", body=body)
            return [h["_source"] for h in resp["hits"]["hits"]]
        except Exception as e:
            logger.warning("Historique OpenSearch indisponible: %s", e)
            return []

    # ------------------------------------------------------------------
    # Classification de l'attaque à partir des alertes internes
    # ------------------------------------------------------------------
    def _build_attack_profile(
        self,
        alerts: list[dict],
        abuse:  AbuseReport,
    ) -> AttackProfile:

        if not alerts:
            return AttackProfile()

        type_votes: dict[str, int] = {}
        services:   set[str]       = set()
        rule_counts: dict[str, int] = {}

        PORT_MAP: dict[str, str] = {
            "22": "SSH",   "3389": "RDP",   "80": "HTTP",  "443": "HTTPS",
            "21": "FTP",   "25":   "SMTP",  "3306": "MySQL", "5432": "PostgreSQL",
            "6379": "Redis", "9200": "OpenSearch", "27017": "MongoDB",
            "8080": "HTTP-Alt", "8443": "HTTPS-Alt",
        }

        for alert in alerts:
            rule     = alert.get("rule", {})
            rule_id  = str(rule.get("id", ""))
            rule_desc= rule.get("description", "")
            dstport  = str(alert.get("data", {}).get("dstport", ""))

            # Top règles déclenchées
            key = f"{rule_id}: {rule_desc[:55]}"
            rule_counts[key] = rule_counts.get(key, 0) + 1

            # Service cible
            if dstport:
                services.add(PORT_MAP.get(dstport, f"Port {dstport}"))

            # Vote pour le type d'attaque
            desc_lower = rule_desc.lower()
            if any(w in desc_lower for w in ["brute", "bruteforce", "login", "auth", "password", "credential"]):
                type_votes["bruteforce"] = type_votes.get("bruteforce", 0) + 1
            elif any(w in desc_lower for w in ["scan", "probe", "sweep", "recon", "enumerat"]):
                type_votes["portscan"]   = type_votes.get("portscan",   0) + 1
            elif any(w in desc_lower for w in ["ddos", "flood", "dos", "syn ", "udp flood", "amplification"]):
                type_votes["ddos"]       = type_votes.get("ddos",       0) + 1
            elif any(w in desc_lower for w in ["exploit", "injection", "overflow", "shellcode", "payload", "rce", "cve-"]):
                type_votes["exploit"]    = type_votes.get("exploit",    0) + 1
            elif any(w in desc_lower for w in ["web", "http", "sql", "xss", "lfi", "rfi", "traversal", "upload"]):
                type_votes["webattack"]  = type_votes.get("webattack",  0) + 1

        # Boost via catégories AbuseIPDB (poids x3)
        CAT_MAP = {
            "DDoS Attack":      "ddos",       "Brute-Force":    "bruteforce",
            "SSH Brute-Force":  "bruteforce", "FTP Brute-Force":"bruteforce",
            "Port Scan":        "portscan",   "Web App Attack":  "webattack",
            "SQL Injection":    "webattack",  "Hacking":        "exploit",
            "Bad Web Bot":      "webattack",  "Exploited Host":  "exploit",
        }
        for cat in abuse.categories:
            t = CAT_MAP.get(cat)
            if t:
                type_votes[t] = type_votes.get(t, 0) + 3

        attack_type = max(type_votes, key=type_votes.get) if type_votes else "unknown"

        SUB_TYPE_MAP = {
            "bruteforce": "Credential Stuffing / Password Spray",
            "portscan":   "Network Reconnaissance (Nmap / Masscan style)",
            "ddos":       "Volumetric ou Application Layer",
            "exploit":    "Remote Code Execution / Exploit connu",
            "webattack":  "OWASP Top 10 (SQLi, XSS, LFI, RCE Web…)",
            "unknown":    "Indéterminé",
        }

        # Timeline
        timestamps = sorted(
            a.get("@timestamp", "") for a in alerts if a.get("@timestamp")
        )
        first = timestamps[0]  if timestamps else ""
        last  = timestamps[-1] if timestamps else ""

        # Intensité
        cnt = len(alerts)
        if   cnt >= 500: intensity = "critical"
        elif cnt >= 100: intensity = "high"
        elif cnt >= 20:  intensity = "medium"
        else:            intensity = "low"

        # Requêtes par minute
        rpm = 0.0
        if len(timestamps) >= 2:
            try:
                t0 = datetime.fromisoformat(first.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(last.replace("Z", "+00:00"))
                minutes = max((t1 - t0).total_seconds() / 60.0, 1.0)
                rpm = round(cnt / minutes, 1)
            except Exception:
                pass

        top_rules = sorted(
            [{"rule": k, "count": v} for k, v in rule_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        return AttackProfile(
            type=attack_type,
            sub_type=SUB_TYPE_MAP.get(attack_type, ""),
            intensity=intensity,
            first_seen=first,
            last_seen=last,
            alert_count=cnt,
            targeted_services=list(services)[:8],
            top_rules=top_rules,
            requests_per_minute=rpm,
        )

    # ------------------------------------------------------------------
    # Évaluation du risque global (0-100) — délègue au scorer unifié
    # ------------------------------------------------------------------
    def _assess_risk(
        self,
        abuse:   AbuseReport,
        vt:      VirusTotalReport,
        profile: AttackProfile,
        geo:     IpGeoInfo,
    ) -> RiskAssessment:
        """
        Construit un faisceau de preuves (`Evidence`) puis délègue au scorer
        déterministe unique `services.scoring.compute_verdict`. Garantit que
        l'investigation OSINT et l'enrichissement temps réel notent à l'identique.
        """
        ev = Evidence(
            abuse_confidence=abuse.confidence_score,
            abuse_total_reports=abuse.total_reports,
            abuse_categories=abuse.categories,
            vt_malicious=vt.malicious,
            vt_suspicious=vt.suspicious,
            attack_type=profile.type,
            attack_intensity=profile.intensity,
            attack_alert_count=profile.alert_count,
            attack_rpm=profile.requests_per_minute,
            targeted_services=profile.targeted_services,
            is_proxy=geo.is_proxy,
            is_hosting=geo.is_hosting,
            asn=geo.asn,
            asn_name=geo.asn_name,
            isp=geo.isp,
        )
        return compute_verdict(ev)

    # ------------------------------------------------------------------
    # Analyse IA bornée — rédige le rapport, NE décide PAS du verdict
    # ------------------------------------------------------------------
    async def _ai_analyze(
        self,
        ip:      str,
        geo:     IpGeoInfo,
        abuse:   AbuseReport,
        vt:      VirusTotalReport,
        profile: AttackProfile,
        risk:    RiskAssessment,
    ) -> AiAnalysis:
        """
        Appelle le LLM borné avec le verdict DÉJÀ calculé. Le modèle ne fait que
        rédiger résumé + récit + remédiation. Repli heuristique garanti.
        """
        ctx = {
            "ip": ip,
            "verdict": risk.verdict,
            "score": risk.score,
            "confidence": risk.confidence,
            "level": risk.level,
            "factors": risk.factors,
            "geo": {
                "country": geo.country, "city": geo.city,
                "isp": geo.isp, "org": geo.org, "asn": geo.asn,
                "is_proxy": geo.is_proxy, "is_hosting": geo.is_hosting,
            },
            "abuse": {"confidence": abuse.confidence_score, "reports": abuse.total_reports,
                      "categories": abuse.categories},
            "virustotal": {"malicious": vt.malicious, "suspicious": vt.suspicious},
            "attack_profile": {
                "type": profile.type, "sub_type": profile.sub_type,
                "intensity": profile.intensity, "alert_count": profile.alert_count,
                "targeted_services": profile.targeted_services,
            },
            "recommended_actions": [a.model_dump() for a in risk.recommended_actions],
        }
        try:
            return await llm_analyze(ctx)
        except Exception as e:
            logger.warning("Analyse IA échouée (%s) — rapport sans IA", e)
            return AiAnalysis(
                summary=f"Verdict {risk.verdict} (score {risk.score}/100).",
                narrative="Analyse IA indisponible.",
                generated_by="unavailable",
            )
