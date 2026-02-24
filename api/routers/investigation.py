"""
Router Investigation OSINT — /api/v1/investigate
Analyse complète d'une IP suspecte : géo, AbuseIPDB, VT, RDAP, historique interne
"""
import ipaddress
import logging

from fastapi import APIRouter, HTTPException, Depends

from api.services.investigation import InvestigationService, InvestigationReport
from api.core.security import require_analyst

logger = logging.getLogger(__name__)
router = APIRouter()
_svc   = InvestigationService()


@router.get(
    "/{ip}",
    response_model=InvestigationReport,
    summary="Investigation OSINT complète d'une IP",
    description="""
    Orchestre une investigation multi-sources en parallèle :
    - Géolocalisation + ISP + ASN (ip-api.com)
    - Score de confiance AbuseIPDB + commentaires
    - Rapport VirusTotal (moteurs antivirus)
    - WHOIS/RDAP (ARIN/RIPE/APNIC)
    - PTR/Reverse DNS
    - Historique de NOS propres alertes liées à cette IP
    - Classification de l'attaque (DDoS, bruteforce, scan, exploit, web attack)
    - Score de risque 0-100 + actions recommandées
    """,
)
async def investigate_ip(
    ip: str,
    _user=Depends(require_analyst),
) -> InvestigationReport:
    """
    Retourne un rapport d'investigation complet sur l'IP fournie.
    Nécessite le rôle analyst ou admin.
    """
    # Validation de l'adresse IP
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Adresse IP invalide : {ip}")

    # Rejeter les IPs privées / locales (pas d'investigation externe utile)
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
        raise HTTPException(
            status_code=422,
            detail=(
                f"L'IP {ip} est une adresse privée/locale — "
                "l'investigation externe ne s'applique pas."
            ),
        )

    logger.info("Investigation demandée pour %s par %s", ip, _user.username)
    report = await _svc.investigate(ip)
    return report
