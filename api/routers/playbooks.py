"""
Router — Playbooks
Déclenchement manuel et confirmation d'actions.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.playbooks import PlaybookEngine, PlaybookTrigger

router = APIRouter()
logger = logging.getLogger(__name__)


class PlaybookRunRequest(BaseModel):
    mitre_id: str
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    agent_ip: Optional[str] = None
    src_ip: Optional[str] = None
    alert_id: Optional[str] = None
    rule_desc: Optional[str] = None


@router.get("", summary="Liste des playbooks disponibles")
async def list_playbooks():
    """Liste tous les playbooks disponibles et leurs triggers MITRE."""
    return {
        "playbooks": [
            {
                "mitre_id": trigger.value,
                "name": trigger.name,
                "description": f"Playbook pour {trigger.value}",
            }
            for trigger in PlaybookTrigger
        ]
    }


@router.post("/run", summary="Déclencher un playbook manuellement")
async def run_playbook(request: PlaybookRunRequest):
    """
    Déclenche manuellement un playbook pour un MITRE ID donné.
    Utile pour les tests ou les réponses manuelles.
    """
    engine = PlaybookEngine()
    context = {
        "agent_id":   request.agent_id,
        "agent_name": request.agent_name,
        "agent_ip":   request.agent_ip,
        "src_ip":     request.src_ip,
        "alert_id":   request.alert_id,
        "rule_desc":  request.rule_desc,
        "mitre_id":   request.mitre_id,
    }

    # Vérifier que le MITRE ID est connu
    known_ids = [t.value for t in PlaybookTrigger]
    if request.mitre_id not in known_ids:
        logger.warning(
            "Playbook inconnu %s — exécution du fallback notify_analyst",
            request.mitre_id,
        )

    import asyncio
    asyncio.create_task(engine.run(request.mitre_id, context))

    return {
        "message": f"Playbook {request.mitre_id} lancé",
        "context": context,
    }


@router.post("/confirm-isolation/{alert_id}", summary="Confirmer l'isolation réseau")
async def confirm_isolation(alert_id: str, confirmed: bool = True):
    """
    Endpoint de callback pour confirmer l'isolation réseau.
    Appelé manuellement par l'analyste ou via Pushover callback.
    """
    if not confirmed:
        return {"message": "Isolation annulée", "alert_id": alert_id}

    from api.services.opensearch import OpenSearchClient
    os = OpenSearchClient()
    alert = await os.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alerte {alert_id} introuvable")

    engine = PlaybookEngine()
    context = {
        "agent_id":   alert.get("agent", {}).get("id"),
        "agent_name": alert.get("agent", {}).get("name"),
        "agent_ip":   alert.get("agent", {}).get("ip"),
        "alert_id":   alert_id,
        "rule_desc":  alert.get("rule", {}).get("description"),
    }

    import asyncio
    asyncio.create_task(engine.action_isolate_network(context))

    return {
        "message": "Isolation réseau déclenchée",
        "alert_id": alert_id,
        "agent_name": context.get("agent_name"),
    }


@router.post("/block-ip", summary="Bloquer une IP manuellement")
async def block_ip(ip: str):
    """Bloque manuellement une IP dans la liste Wazuh."""
    engine = PlaybookEngine()
    await engine.action_block_ip_firewall({"src_ip": ip})
    return {"message": f"IP {ip} bloquée via Wazuh CDB list"}
