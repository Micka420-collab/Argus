"""
Router Système — /api/v1/system
===============================
Informations serveur + actions d'exploitation (mise à jour GitHub, redémarrage).
Les actions sont réservées au rôle ADMIN et déléguées au conteneur « argus-ops »
via une file Redis (soc-api n'a pas accès à Docker).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from api.core.config import settings
from api.core.security import require_admin, require_analyst
from api.services import ops

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/info",
    summary="Informations sur le serveur Argus",
    description="Version, environnement, configuration IA et état de la dernière opération.",
)
async def info(_user=Depends(require_analyst)):
    op = await ops.status()
    return {
        "name":        settings.APP_NAME,
        "version":     settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model":    settings.LLM_MODEL or "",
        "pqc_jwt":      settings.PQC_JWT,
        "ops":          op,
    }


@router.get("/ops-status", summary="État de la dernière opération serveur")
async def ops_status(_user=Depends(require_analyst)):
    return await ops.status()


@router.post(
    "/update",
    summary="Mettre à jour Argus depuis GitHub",
    description="Déclenche `git pull` + reconstruction des images (via l'agent ops). Admin uniquement.",
)
async def update(_user=Depends(require_admin)):
    ok = await ops.enqueue("update")
    if not ok:
        raise HTTPException(503, "Agent d'exploitation indisponible (Redis/argus-ops).")
    return {"queued": True, "command": "update",
            "message": "Mise à jour lancée. Le serveur va se reconstruire (1-3 min)."}


@router.post(
    "/restart",
    summary="Redémarrer l'application Argus",
    description="Redémarre les services applicatifs (api, frontend, nginx) via l'agent ops. Admin uniquement.",
)
async def restart(_user=Depends(require_admin)):
    ok = await ops.enqueue("restart")
    if not ok:
        raise HTTPException(503, "Agent d'exploitation indisponible (Redis/argus-ops).")
    return {"queued": True, "command": "restart",
            "message": "Redémarrage des services applicatifs en cours…"}
