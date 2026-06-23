"""
SOC Platform — Service ASM / CTEM
=================================
Priorisation de l'exposition réelle : **CVSS × EPSS × KEV × valeur métier**.

- EPSS (FIRST.org) : probabilité d'exploitation à 30 jours.
- KEV (CISA) : vulnérabilités activement exploitées (catalogue mis en cache 24 h).
- Score 0-100 déterministe + tier (critical/high/medium/low).
- Registre (assets + findings) stocké dans OpenSearch ; enrichissement gracieux
  (repli si EPSS/KEV/OpenSearch indisponibles).

NB : le scan actif (subfinder/httpx/nuclei…) est un point d'intégration externe
(`source="scan"`) ; ce service fournit l'inventaire, l'enrichissement et la
priorisation — le cœur CTEM, indépendant des binaires de scan.
"""
from __future__ import annotations

import json
import uuid
import logging
from datetime import datetime, timezone

from api.core.config import settings
from api.core.http import get_http_client
from api.models.exposure import (
    ExposureAsset, Finding, FindingCreate, FindingStatus, BusinessValue,
)

logger = logging.getLogger(__name__)

ASSETS_INDEX   = settings.OPENSEARCH_INDEX_EXPOSURE + "-assets"
FINDINGS_INDEX = settings.OPENSEARCH_INDEX_EXPOSURE + "-findings"

_BV_WEIGHT = {
    BusinessValue.CRITICAL: 1.0, BusinessValue.HIGH: 0.8,
    BusinessValue.MEDIUM: 0.6, BusinessValue.LOW: 0.4,
}


# ===========================================================================
# Priorisation déterministe
# ===========================================================================
def compute_priority(cvss: float, epss: float, in_kev: bool,
                     business_value: str = "medium") -> tuple[int, str]:
    """
    Retourne (score 0-100, tier). KEV impose une priorité plancher (exploité dans
    la nature → attention immédiate, même à CVSS modéré).
    """
    cvss_c   = max(0.0, min(cvss, 10.0)) / 10.0
    exploit  = 1.0 if in_kev else max(0.0, min(epss, 1.0))
    bv       = _BV_WEIGHT.get(business_value, 0.6)
    raw      = (0.5 * cvss_c + 0.5 * exploit) * bv
    score    = round(raw * 100)
    if in_kev:
        score = max(score, 80)          # plancher KEV
    score = max(0, min(score, 100))
    tier = ("critical" if score >= 80 else "high" if score >= 60
            else "medium" if score >= 40 else "low")
    return score, tier


# ===========================================================================
# Enrichissement EPSS / KEV
# ===========================================================================
async def _redis():
    try:
        from api.services.deduplication import get_redis
        return await get_redis()
    except Exception:
        return None


async def fetch_epss(cve: str) -> tuple[float, float]:
    """(epss, percentile) — 0,0 si indisponible."""
    if not cve:
        return 0.0, 0.0
    try:
        async with get_http_client(timeout=8) as client:
            r = await client.get("https://api.first.org/data/v1/epss", params={"cve": cve})
            data = (r.json() or {}).get("data", [])
            if data:
                return float(data[0].get("epss", 0) or 0), float(data[0].get("percentile", 0) or 0)
    except Exception as e:
        logger.debug("EPSS indisponible pour %s (%s)", cve, e)
    return 0.0, 0.0


async def _kev_catalog() -> set[str]:
    """Ensemble des CVE du catalogue CISA KEV (cache Redis 24 h)."""
    r = await _redis()
    if r:
        try:
            cached = await r.get("kev:catalog")
            if cached:
                return set(json.loads(cached))
        except Exception:
            pass
    cves: set[str] = set()
    try:
        async with get_http_client(timeout=20) as client:
            resp = await client.get(
                "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
            )
            for v in (resp.json() or {}).get("vulnerabilities", []):
                cid = v.get("cveID")
                if cid:
                    cves.add(cid)
        if r and cves:
            await r.setex("kev:catalog", 86400, json.dumps(sorted(cves)))
    except Exception as e:
        logger.info("Catalogue KEV indisponible (%s)", e)
    return cves


async def in_kev(cve: str) -> bool:
    return bool(cve) and cve in await _kev_catalog()


# ===========================================================================
# Stockage OpenSearch
# ===========================================================================
async def _client():
    from api.services.opensearch import OpenSearchClient
    return await OpenSearchClient().get_client()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _asset_value(asset_name: str) -> str:
    """Valeur métier d'un asset (depuis le registre), défaut medium."""
    try:
        client = await _client()
        resp = await client.search(
            index=ASSETS_INDEX,
            body={"size": 1, "query": {"term": {"name.keyword": asset_name}}},
        )
        hits = resp.get("hits", {}).get("hits", [])
        if hits:
            return hits[0]["_source"].get("business_value", BusinessValue.MEDIUM)
    except Exception:
        pass
    return BusinessValue.MEDIUM


# ---- Assets ---------------------------------------------------------------
async def list_assets() -> list[dict]:
    try:
        client = await _client()
        resp = await client.search(index=ASSETS_INDEX, body={"size": 500, "query": {"match_all": {}}})
        return [h["_source"] for h in resp.get("hits", {}).get("hits", [])]
    except Exception as e:
        logger.info("list_assets indisponible (%s)", e)
        return []


async def upsert_asset(asset: ExposureAsset) -> ExposureAsset:
    asset.id = asset.id or uuid.uuid4().hex[:12]
    asset.first_seen = asset.first_seen or _now()
    asset.last_seen = _now()
    try:
        client = await _client()
        await client.index(index=ASSETS_INDEX, id=asset.id, body=asset.model_dump(), refresh=True)
    except Exception as e:
        logger.warning("upsert_asset impossible (%s)", e)
    return asset


# ---- Findings -------------------------------------------------------------
async def add_finding(payload: FindingCreate) -> Finding:
    epss, percentile = await fetch_epss(payload.cve)
    kev = await in_kev(payload.cve)
    bv = await _asset_value(payload.asset)
    score, tier = compute_priority(payload.cvss, epss, kev, bv)

    finding = Finding(
        id=uuid.uuid4().hex[:12],
        asset=payload.asset,
        title=payload.title,
        cve=payload.cve,
        cvss=payload.cvss,
        epss=epss,
        epss_percentile=percentile,
        in_kev=kev,
        priority_score=score,
        priority_tier=tier,
        status=FindingStatus.OPEN,
        source=payload.source,
        description=payload.description,
        created_at=_now(),
        updated_at=_now(),
    )
    try:
        client = await _client()
        await client.index(index=FINDINGS_INDEX, id=finding.id, body=finding.model_dump(), refresh=True)
    except Exception as e:
        logger.warning("add_finding: persistance impossible (%s)", e)

    if finding.in_kev:
        try:
            from api.services.webhooks import emit
            await emit("exposure_kev", {
                "id": finding.id, "asset": finding.asset, "cve": finding.cve,
                "title": finding.title, "priority": finding.priority_score,
                "tier": finding.priority_tier,
            })
        except Exception as e:
            logger.debug("Webhook exposition impossible (%s)", e)
    return finding


async def list_findings(tier: str | None = None, status: str | None = None, size: int = 200) -> list[dict]:
    try:
        client = await _client()
        must = []
        if tier:
            must.append({"term": {"priority_tier": tier}})
        if status:
            must.append({"term": {"status": status}})
        query = {"bool": {"must": must}} if must else {"match_all": {}}
        resp = await client.search(
            index=FINDINGS_INDEX,
            body={"size": size, "query": query, "sort": [{"priority_score": {"order": "desc"}}]},
        )
        return [h["_source"] for h in resp.get("hits", {}).get("hits", [])]
    except Exception as e:
        logger.info("list_findings indisponible (%s)", e)
        return []


async def set_finding_status(finding_id: str, status: str) -> dict:
    try:
        client = await _client()
        resp = await client.get(index=FINDINGS_INDEX, id=finding_id)
        raw = resp["_source"]
    except Exception:
        raise ValueError("Finding introuvable")
    raw["status"] = status
    raw["updated_at"] = _now()
    try:
        client = await _client()
        await client.index(index=FINDINGS_INDEX, id=finding_id, body=raw, refresh=True)
    except Exception as e:
        logger.warning("set_finding_status impossible (%s)", e)
    return raw


async def stats() -> dict:
    findings = await list_findings(size=1000)
    by_tier: dict[str, int] = {}
    kev_count = 0
    open_count = 0
    for f in findings:
        by_tier[f.get("priority_tier", "low")] = by_tier.get(f.get("priority_tier", "low"), 0) + 1
        if f.get("in_kev"):
            kev_count += 1
        if f.get("status") == "open":
            open_count += 1
    return {"total": len(findings), "open": open_count, "kev": kev_count,
            "by_tier": by_tier, "assets": len(await list_assets())}
