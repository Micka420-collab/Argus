"""
SOC Platform — Triage assisté des rapports VDP (réutilise le LLM borné)
=======================================================================
- Détection de doublon : recherche les rapports existants sur le même asset /
  type de vulnérabilité (similarité de caractéristiques, sans embeddings).
- Sévérité suggérée : dérivée du CVSS (déterministe).
- Résumé de triage : rédigé par le LLM borné (repli heuristique).
"""
from __future__ import annotations

import logging

from api.models.vdp import Report, TriageInfo
from api.services import llm

logger = logging.getLogger(__name__)


def _similar(a: str, b: str) -> float:
    """Similarité Jaccard simple sur les mots (0..1)."""
    sa = set((a or "").lower().split())
    sb = set((b or "").lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


async def _find_duplicate(report: Report) -> str:
    """Renvoie l'id d'un doublon probable, ou ""."""
    try:
        from api.services.vdp import list_reports
        existing = await list_reports(size=200)
    except Exception:
        return ""
    for r in existing:
        if r.get("id") == report.id:
            continue
        same_asset = report.asset and r.get("asset") == report.asset
        same_type  = report.vuln_type and r.get("vuln_type") == report.vuln_type
        title_sim  = _similar(report.title, r.get("title", ""))
        if (same_asset and same_type) or title_sim >= 0.6:
            return r.get("id", "")
    return ""


async def triage_report(report: Report) -> TriageInfo:
    dup_id = await _find_duplicate(report)

    summary = ""
    generated_by = "heuristic"
    prompt = (
        f"Rapport de vulnérabilité à trier.\n"
        f"Titre: {report.title}\nType: {report.vuln_type}\nAsset: {report.asset}\n"
        f"CVSS: {report.cvss_vector} (score {report.cvss_score}, {report.severity})\n"
        f"Description: {report.description[:1500]}\n\n"
        f"Donne en 2-3 phrases un résumé de triage pour un analyste : nature de la "
        f"faille, impact probable, et prochaine action recommandée."
    )
    text = await llm.complete(
        "Tu es un triager bug-bounty senior. Sois factuel et concis, en français.",
        prompt,
    )
    if text:
        summary = text[:800]
        generated_by = f"{(llm.settings.LLM_PROVIDER or 'none')}"
    else:
        summary = (
            f"Vulnérabilité de type « {report.vuln_type or 'non précisé'} » sur "
            f"{report.asset or 'asset non précisé'} — sévérité {report.severity} "
            f"(CVSS {report.cvss_score}). "
            + ("Doublon probable — vérifier avant traitement. " if dup_id else "")
            + "Vérifier la reproductibilité puis décider de l'acceptation."
        )

    return TriageInfo(
        summary=summary,
        ai_severity=report.severity,
        is_duplicate=bool(dup_id),
        duplicate_of=dup_id,
        notes="",
        generated_by=generated_by,
    )
