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
from api.services.opensearch import OpenSearchClient

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


class RecommendedAction(BaseModel):
    action:      str
    label:       str
    description: str
    priority:    str   # high|medium|low


class RiskAssessment(BaseModel):
    score:               int                     = 0
    level:               str                     = "low"
    factors:             list[str]               = []
    recommended_actions: list[RecommendedAction] = []


class InvestigationReport(BaseModel):
    ip:             str
    timestamp:      str
    geo:            IpGeoInfo
    abuse:          AbuseReport
    virustotal:     VirusTotalReport
    attack_profile: AttackProfile
    risk:           RiskAssessment
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
    async def investigate(self, ip: str) -> InvestigationReport:
        logger.info("Investigation OSINT démarrée pour l'IP : %s", ip)

        # Vérifier le cache Redis pour un rapport complet (TTL 1 heure)
        cache_key = f"investigation:{ip}"
        cached = await self._cache_get(cache_key)
        if cached:
            logger.info("Investigation récupérée depuis le cache Redis pour %s", ip)
            return InvestigationReport(**cached)

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

        report = InvestigationReport(
            ip=ip,
            timestamp=datetime.now(timezone.utc).isoformat(),
            geo=geo,
            abuse=abuse,
            virustotal=vt,
            attack_profile=profile,
            risk=risk,
            raw_rdap=rdap,
        )

        # Mettre en cache pour 1 heure (économise le quota AbuseIPDB/VT)
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
            async with httpx.AsyncClient(timeout=6) as client:
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
            async with httpx.AsyncClient(timeout=8) as client:
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
            async with httpx.AsyncClient(timeout=8) as client:
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
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
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
    # Évaluation du risque global (0-100)
    # ------------------------------------------------------------------
    def _assess_risk(
        self,
        abuse:   AbuseReport,
        vt:      VirusTotalReport,
        profile: AttackProfile,
        geo:     IpGeoInfo,
    ) -> RiskAssessment:

        score   = 0
        factors: list[str]              = []
        actions: list[RecommendedAction] = []

        # AbuseIPDB confidence score
        if   abuse.confidence_score >= 90: score += 40; factors.append(f"Score AbuseIPDB très élevé : {abuse.confidence_score}/100")
        elif abuse.confidence_score >= 50: score += 25; factors.append(f"Score AbuseIPDB élevé : {abuse.confidence_score}/100")
        elif abuse.confidence_score >= 20: score += 10; factors.append(f"Score AbuseIPDB modéré : {abuse.confidence_score}/100")

        # Nombre total de signalements
        if   abuse.total_reports >= 100: score += 15; factors.append(f"Signalée {abuse.total_reports}× sur AbuseIPDB")
        elif abuse.total_reports >= 10:  score += 8;  factors.append(f"Signalée {abuse.total_reports}× sur AbuseIPDB")

        # VirusTotal détections
        if   vt.malicious >= 10: score += 25; factors.append(f"Détectée malveillante par {vt.malicious} moteurs VT")
        elif vt.malicious >= 5:  score += 20; factors.append(f"Détectée malveillante par {vt.malicious} moteurs VT")
        elif vt.malicious >= 1:  score += 10; factors.append(f"Détectée par {vt.malicious} moteur(s) VT")

        # Intensité de l'attaque interne
        intensity_pts = {"critical": 20, "high": 12, "medium": 7, "low": 3}
        score += intensity_pts.get(profile.intensity, 0)
        if profile.intensity in ("critical", "high"):
            factors.append(f"Intensité : {profile.intensity.upper()} ({profile.alert_count} alertes, {profile.requests_per_minute} req/min)")

        # Infrastructure suspecte
        if geo.is_proxy:
            score += 10
            factors.append("IP identifiée comme proxy / VPN / Tor exit node")
        if geo.is_hosting:
            score += 5
            factors.append("IP hébergée dans un datacenter (VPS/cloud)")

        # Catégories dangereuses connues
        DANGER_CATS = {"DDoS Attack", "Brute-Force", "SSH Brute-Force", "Web App Attack", "Hacking", "SQL Injection"}
        matched = DANGER_CATS & set(abuse.categories)
        if matched:
            score += 8
            factors.append(f"Catégories connues : {', '.join(matched)}")

        score = min(score, 100)
        if   score >= 80: level = "critical"
        elif score >= 55: level = "high"
        elif score >= 30: level = "medium"
        else:             level = "low"

        # Actions recommandées
        if score >= 50:
            actions.append(RecommendedAction(
                action="block_ip",
                label="🚫 Bloquer l'IP immédiatement",
                description="Ajouter à la liste noire Wazuh + règle iptables/nftables sur tous les hôtes",
                priority="high",
            ))
        if score >= 70 and geo.asn:
            actions.append(RecommendedAction(
                action="block_asn",
                label=f"🌐 Bloquer l'ASN entier ({geo.asn})",
                description=f"Toutes les IPs de {geo.asn_name or geo.isp} seront bloquées (attention : faux positifs possibles)",
                priority="medium",
            ))
        if profile.type == "ddos":
            actions.append(RecommendedAction(
                action="rate_limit",
                label="⚡ Appliquer un rate limit agressif",
                description="Limiter à 10 req/s depuis cette IP (nginx limit_req ou iptables --hashlimit)",
                priority="high",
            ))
        if abuse.confidence_score >= 30:
            actions.append(RecommendedAction(
                action="report_abuseipdb",
                label="📋 Signaler sur AbuseIPDB",
                description="Contribuer à la protection communautaire en soumettant un rapport",
                priority="low",
            ))
        if profile.type == "bruteforce":
            actions.append(RecommendedAction(
                action="change_credentials",
                label="🔑 Vérifier les comptes ciblés",
                description=f"Services visés : {', '.join(profile.targeted_services or ['?'])} — vérifier logs d'accès",
                priority="high",
            ))
        actions.append(RecommendedAction(
            action="monitor",
            label="👁️ Surveillance renforcée 72h",
            description="Créer une règle d'alerte prioritaire pour surveiller cette IP et son sous-réseau /24",
            priority="low",
        ))

        return RiskAssessment(
            score=score,
            level=level,
            factors=factors,
            recommended_actions=actions,
        )
