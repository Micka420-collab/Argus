"""
Router Analyste IA autonome — /api/v1/ai
========================================
Déclenchement manuel de l'agent d'investigation autonome, consultation des
rapports persistés, et boucle de feedback analyste (auto-amélioration RAG).
"""
import ipaddress
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.core.security import require_analyst
from api.services.opensearch import OpenSearchClient
from api.services.ai_investigation import AiInvestigationAgent, list_reports, get_report
from api.services import feedback as feedback_svc

logger = logging.getLogger(__name__)
router = APIRouter()
_agent = AiInvestigationAgent()


@router.get("/reports", summary="Liste des investigations autonomes")
async def reports(
    verdict: str | None = Query(None, description="malicious|benign|inconclusive"),
    size: int = Query(50, ge=1, le=200),
    _user=Depends(require_analyst),
):
    return {"items": await list_reports(size=size, verdict=verdict)}


@router.get("/report/{report_id}", summary="Détail d'une investigation autonome")
async def report(report_id: str, _user=Depends(require_analyst)):
    rep = await get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    return rep


@router.post("/investigate/{alert_id}", summary="Investiguer une alerte (agent autonome)")
async def investigate_alert(alert_id: str, _user=Depends(require_analyst)):
    alert = await OpenSearchClient().get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alerte {alert_id} introuvable")
    logger.info("Investigation IA manuelle (alerte %s) par %s", alert_id, _user.get("username", "?"))
    return await _agent.run(alert, source="manual")


@router.post("/investigate-ip/{ip}", summary="Investiguer une IP (agent autonome)")
async def investigate_ip(ip: str, _user=Depends(require_analyst)):
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"IP invalide : {ip}")
    synthetic = {"id": "", "data": {"srcip": ip}, "rule": {}, "agent": {}}
    logger.info("Investigation IA manuelle (IP %s) par %s", ip, _user.get("username", "?"))
    return await _agent.run(synthetic, source="manual")


@router.post("/feedback/{report_id}", summary="Feedback analyste (corriger/valider un verdict)")
async def submit_feedback(
    report_id: str,
    corrected_verdict: str = Query(..., description="malicious|benign|inconclusive"),
    rationale: str = Query("", description="Justification (sera réutilisée par le RAG)"),
    _user=Depends(require_analyst),
):
    if corrected_verdict not in ("malicious", "benign", "inconclusive"):
        raise HTTPException(status_code=400, detail="Verdict corrigé invalide")
    rep = await get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Rapport introuvable")

    osint_attack = (rep.get("verdict", {}) or {})
    ok = await feedback_svc.store_feedback(
        report_id=report_id,
        ip=rep.get("ip", ""),
        attack_type=(rep.get("alert_meta", {}) or {}).get("rule_desc", "unknown"),
        asn="",
        original_verdict=rep.get("decision", "inconclusive"),
        corrected_verdict=corrected_verdict,
        rationale=rationale,
        analyst=_user.get("username", "?"),
    )
    return {"stored": ok, "report_id": report_id, "corrected_verdict": corrected_verdict}
