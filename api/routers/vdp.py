"""
Router VDP / Bug-Bounty — /api/v1/vdp (pilier YesWeHack)
========================================================
Soumission de rapports (chercheurs), triage (analystes/triagers), programmes,
calcul CVSS et statistiques.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.core.security import get_current_user, require_triager, require_admin
from api.models.vdp import Report, ReportCreate, Program, StatusUpdate
from api.services import vdp as vdp_svc

logger = logging.getLogger(__name__)
router = APIRouter()


# ---- Soumission (chercheur authentifié) -----------------------------------
@router.post("/reports", response_model=Report, summary="Soumettre un rapport de vulnérabilité")
async def submit_report(payload: ReportCreate, user=Depends(get_current_user)):
    if not payload.title.strip() or not payload.description.strip():
        raise HTTPException(status_code=400, detail="Titre et description requis")
    return await vdp_svc.create_report(payload, researcher=user.get("username", "anonyme"))


# ---- Triage (analyste / triager) ------------------------------------------
@router.get("/reports", summary="Lister les rapports VDP")
async def list_reports(
    status: str | None = Query(None, description="new|triaging|need_info|accepted|resolved|duplicate|out_of_scope|spam|rejected"),
    size: int = Query(100, ge=1, le=500),
    _user=Depends(require_triager),
):
    return {"items": await vdp_svc.list_reports(status=status, size=size)}


@router.get("/reports/{report_id}", summary="Détail d'un rapport")
async def get_report(report_id: str, _user=Depends(require_triager)):
    rep = await vdp_svc.get_report(report_id)
    if not rep:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    return rep


@router.patch("/reports/{report_id}/status", summary="Changer le statut (machine à états)")
async def change_status(report_id: str, update: StatusUpdate, user=Depends(require_triager)):
    try:
        return await vdp_svc.transition(report_id, update.status, user.get("username", "?"), update.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---- Programmes -----------------------------------------------------------
@router.get("/programs", summary="Lister les programmes")
async def list_programs(_user=Depends(get_current_user)):
    progs = await vdp_svc.list_programs()
    if not progs:
        prog = await vdp_svc.ensure_default_program()
        progs = [prog.model_dump()]
    return {"items": progs}


@router.post("/programs", response_model=Program, summary="Créer un programme")
async def create_program(program: Program, _user=Depends(require_admin)):
    return await vdp_svc.create_program(program)


# ---- Utilitaires ----------------------------------------------------------
@router.get("/cvss", summary="Calculer un score CVSS v3.1")
async def cvss(vector: str = Query(..., description="CVSS:3.1/AV:N/AC:L/..."), _user=Depends(get_current_user)):
    score, severity = vdp_svc.compute_cvss(vector)
    return {"vector": vector, "score": score, "severity": severity}


@router.get("/stats", summary="Statistiques VDP")
async def stats(_user=Depends(require_triager)):
    return await vdp_svc.stats()
