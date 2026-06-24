"""
Router Réseau / Machines — /api/v1/network
==========================================
Liste les machines présentes sur le réseau (agents Wazuh) et fournit la
procédure pour en connecter une nouvelle au SOC. Lecture : rôle analyst/admin.
"""
import logging

from fastapi import APIRouter, Depends

from api.core.security import require_analyst
from api.services import wazuh

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/agents",
    summary="Machines surveillées (agents Wazuh)",
    description="Liste les machines présentes sur le réseau et leur état (actif, déconnecté…).",
)
async def agents(_user=Depends(require_analyst)):
    return await wazuh.list_agents()


@router.get(
    "/enroll",
    summary="Comment connecter une machine au SOC",
    description="Adresse du manager + commandes d'installation de l'agent (Linux/Windows).",
)
async def enroll(_user=Depends(require_analyst)):
    return wazuh.enroll_info()
