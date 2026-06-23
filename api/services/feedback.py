"""
SOC Platform — Mémoire de feedback analyste (RAG léger)
=======================================================

Auto-amélioration **sans fine-tuning** (cf. Qevlar) : quand un analyste
corrige/valide le verdict d'une investigation IA, on stocke la décision + sa
justification. Lors d'une future investigation similaire, ces décisions passées
sont récupérées et injectées dans le contexte du nœud de rédaction du rapport.

Implémentation volontairement légère : stockage dans OpenSearch
(`soc-ai-feedback`) avec une **récupération par similarité de caractéristiques**
(type d'attaque, ASN, sous-réseau /24, IP exacte) — pas d'embeddings requis.
La Phase 3 pourra brancher pgvector/sentence-transformers sans changer l'API.

Repli gracieux : si OpenSearch est indisponible, `retrieve_context` renvoie [].
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from api.core.config import settings

logger = logging.getLogger(__name__)

FEEDBACK_INDEX = "soc-ai-feedback"


def _subnet24(ip: str) -> str:
    try:
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3]) + ".0/24"
    except Exception:
        pass
    return ""


async def store_feedback(
    *,
    report_id: str,
    ip: str,
    attack_type: str,
    asn: str,
    original_verdict: str,
    corrected_verdict: str,
    rationale: str,
    analyst: str,
) -> bool:
    """Persiste une correction/validation analyste."""
    doc = {
        "report_id": report_id,
        "ip": ip,
        "subnet24": _subnet24(ip),
        "attack_type": attack_type,
        "asn": asn,
        "original_verdict": original_verdict,
        "corrected_verdict": corrected_verdict,
        "rationale": rationale,
        "analyst": analyst,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        from api.services.opensearch import OpenSearchClient
        client = await OpenSearchClient().get_client()
        await client.index(index=FEEDBACK_INDEX, body=doc, refresh=True)
        logger.info("Feedback stocké pour %s (%s→%s)", ip, original_verdict, corrected_verdict)
        return True
    except Exception as e:
        logger.warning("Stockage feedback impossible (%s)", e)
        return False


async def retrieve_context(
    ip: str,
    attack_type: str,
    asn: str = "",
    k: int = 3,
) -> list[dict[str, Any]]:
    """
    Récupère les décisions analyste passées pertinentes (IP exacte > /24 > ASN >
    type d'attaque). Renvoie une liste de dicts {corrected_verdict, rationale,
    when, match} — vide si rien / OpenSearch indisponible.
    """
    should = []
    if ip:
        should.append({"term": {"ip": ip}})
        sub = _subnet24(ip)
        if sub:
            should.append({"term": {"subnet24": sub}})
    if asn:
        should.append({"term": {"asn": asn}})
    if attack_type and attack_type != "unknown":
        should.append({"term": {"attack_type": attack_type}})
    if not should:
        return []

    try:
        from api.services.opensearch import OpenSearchClient
        client = await OpenSearchClient().get_client()
        resp = await client.search(
            index=FEEDBACK_INDEX,
            body={
                "size": k,
                "query": {"bool": {"should": should, "minimum_should_match": 1}},
                "sort": [{"timestamp": {"order": "desc"}}],
            },
        )
    except Exception as e:
        logger.debug("retrieve_context: OpenSearch indisponible (%s)", e)
        return []

    out: list[dict[str, Any]] = []
    for hit in resp.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        match = (
            "IP exacte" if src.get("ip") == ip else
            "même /24" if src.get("subnet24") == _subnet24(ip) else
            f"même ASN {asn}" if asn and src.get("asn") == asn else
            f"même type « {attack_type} »"
        )
        out.append({
            "corrected_verdict": src.get("corrected_verdict"),
            "rationale": src.get("rationale", ""),
            "when": src.get("timestamp", ""),
            "analyst": src.get("analyst", ""),
            "match": match,
        })
    return out
