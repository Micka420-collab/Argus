"""
Router ASM / CTEM — /api/v1/exposure
====================================
Registre d'exposition priorisé (CVSS × EPSS × KEV × valeur métier).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from api.core.security import require_analyst
from api.models.exposure import ExposureAsset, Finding, FindingCreate, FindingStatusUpdate
from api.services import exposure as svc

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/findings", summary="Findings priorisés")
async def list_findings(
    tier: str | None = Query(None, description="critical|high|medium|low"),
    status: str | None = Query(None, description="open|triaged|mitigated|accepted|false_positive"),
    size: int = Query(200, ge=1, le=1000),
    _user=Depends(require_analyst),
):
    return {"items": await svc.list_findings(tier=tier, status=status, size=size)}


@router.post("/findings", response_model=Finding, summary="Ajouter un finding (enrichi EPSS/KEV)")
async def add_finding(payload: FindingCreate, _user=Depends(require_analyst)):
    if not payload.asset.strip() or not payload.title.strip():
        raise HTTPException(status_code=400, detail="Asset et titre requis")
    return await svc.add_finding(payload)


@router.patch("/findings/{finding_id}/status", summary="Changer le statut d'un finding")
async def set_status(finding_id: str, update: FindingStatusUpdate, _user=Depends(require_analyst)):
    try:
        return await svc.set_finding_status(finding_id, update.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/assets", summary="Inventaire des assets exposés")
async def list_assets(_user=Depends(require_analyst)):
    return {"items": await svc.list_assets()}


@router.post("/assets", response_model=ExposureAsset, summary="Déclarer / mettre à jour un asset")
async def upsert_asset(asset: ExposureAsset, _user=Depends(require_analyst)):
    return await svc.upsert_asset(asset)


@router.get("/cve/{cve}", summary="Enrichissement EPSS/KEV d'un CVE")
async def cve_info(cve: str, _user=Depends(require_analyst)):
    epss, percentile = await svc.fetch_epss(cve)
    kev = await svc.in_kev(cve)
    return {"cve": cve, "epss": epss, "epss_percentile": percentile, "in_kev": kev}


@router.get("/stats", summary="Statistiques d'exposition")
async def stats(_user=Depends(require_analyst)):
    return await svc.stats()
