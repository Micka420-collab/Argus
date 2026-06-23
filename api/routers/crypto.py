"""
Router Posture Post-Quantique — /api/v1/crypto
==============================================
Expose l'auto-évaluation crypto-agility et le CBOM observé (handshakes TLS).
Lecture seule, rôle analyst/admin requis.
"""
import logging

from fastapi import APIRouter, Depends, Query

from api.core.security import require_analyst
from api.services.crypto_inventory import (
    ReadinessReport,
    CbomReport,
    self_assessment,
    build_cbom,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/readiness",
    response_model=ReadinessReport,
    summary="Posture post-quantique de la plateforme",
    description="Note la cryptographie déclarée d'Argus (TLS, certificat, JWT) face à la menace quantique.",
)
async def readiness(_user=Depends(require_analyst)) -> ReadinessReport:
    return self_assessment()


@router.get(
    "/inventory",
    response_model=CbomReport,
    summary="CBOM — inventaire cryptographique observé (TLS)",
    description="Agrège les handshakes TLS vus par Suricata et classe leur résistance quantique.",
)
async def inventory(
    period_hours: int = Query(24, ge=1, le=720),
    _user=Depends(require_analyst),
) -> CbomReport:
    return await build_cbom(period_hours)


@router.get(
    "/jwt-info",
    summary="Algorithme de signature des jetons d'authentification",
    description="Indique si les JWT sont signés en hybride post-quantique (Ed25519 + ML-DSA) et expose les clés publiques.",
)
async def jwt_info(_user=Depends(require_analyst)):
    from api.core.config import settings
    if not settings.PQC_JWT:
        return {"pqc_jwt": False, "algorithm": "HS256",
                "note": "JWT symétrique HS256 (résistant au quantique mais non-asymétrique). "
                        "Activer PQC_JWT=true pour des signatures hybrides Ed25519+ML-DSA."}
    from api.core import pqc
    return {"pqc_jwt": True, **pqc.public_keys()}
