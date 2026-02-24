"""
Router — Incidents
Gestion complète du cycle de vie des incidents de sécurité.
Stockage dans Redis (simple) — remplacer par PostgreSQL en production.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query
import redis.asyncio as aioredis

from api.models.incident import (
    Incident, IncidentCreate, IncidentUpdate,
    IncidentAddNote, TimelineEntry, IncidentStatus
)
from api.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

INCIDENT_PREFIX = "incident:"
INCIDENT_LIST_KEY = "incidents:list"


async def get_redis() -> aioredis.Redis:
    return aioredis.from_url(
        settings.REDIS_URL,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True,
    )


# ----------------------------------------------------------
# CRUD
# ----------------------------------------------------------

@router.get("", summary="Liste des incidents")
async def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Liste tous les incidents avec filtres optionnels."""
    r = await get_redis()
    incident_ids = await r.lrange(INCIDENT_LIST_KEY, 0, -1)

    incidents = []
    for iid in incident_ids:
        raw = await r.get(f"{INCIDENT_PREFIX}{iid}")
        if raw:
            data = json.loads(raw)
            inc = Incident(**data)
            if status and inc.status != status:
                continue
            if severity and inc.severity != severity:
                continue
            if assigned_to and inc.assigned_to != assigned_to:
                continue
            incidents.append(inc)

    # Tri par date de création décroissante
    incidents.sort(key=lambda x: x.created_at, reverse=True)

    # Pagination
    total = len(incidents)
    start = (page - 1) * per_page
    items = incidents[start: start + per_page]

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_next": (start + per_page) < total,
        "items": [i.model_dump() for i in items],
    }


@router.post("", status_code=201, summary="Créer un incident")
async def create_incident(incident_in: IncidentCreate):
    """Crée un nouvel incident de sécurité."""
    r = await get_redis()

    inc = Incident(
        id=str(uuid.uuid4()),
        **incident_in.model_dump(),
        timeline=[
            TimelineEntry(
                action="Incident créé",
                details=f"Sévérité: {incident_in.severity}, Catégorie: {incident_in.category}",
            )
        ],
    )

    # Lier les alertes à cet incident
    if incident_in.alert_ids:
        from api.services.opensearch import OpenSearchClient
        os = OpenSearchClient()
        for alert_id in incident_in.alert_ids:
            await os.update_alert(alert_id, {"incident_id": inc.id})

    await r.set(f"{INCIDENT_PREFIX}{inc.id}", inc.model_dump_json())
    await r.lpush(INCIDENT_LIST_KEY, inc.id)

    return inc


@router.get("/{incident_id}", summary="Détail d'un incident")
async def get_incident(incident_id: str):
    r = await get_redis()
    raw = await r.get(f"{INCIDENT_PREFIX}{incident_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} introuvable")
    return json.loads(raw)


@router.patch("/{incident_id}", summary="Mettre à jour un incident")
async def update_incident(incident_id: str, update: IncidentUpdate):
    r = await get_redis()
    raw = await r.get(f"{INCIDENT_PREFIX}{incident_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} introuvable")

    inc = Incident(**json.loads(raw))
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}

    for field, value in update_data.items():
        setattr(inc, field, value)

    # Si on ferme l'incident
    if update.status in [IncidentStatus.CLOSED, IncidentStatus.RECOVERED]:
        inc.closed_at = datetime.utcnow()
        inc.timeline.append(TimelineEntry(
            action=f"Incident fermé — statut: {update.status}",
            author="analyst",
        ))

    inc.updated_at = datetime.utcnow()
    await r.set(f"{INCIDENT_PREFIX}{inc.id}", inc.model_dump_json())
    return inc


@router.post("/{incident_id}/notes", summary="Ajouter une note")
async def add_note(incident_id: str, note: IncidentAddNote):
    """Ajoute une entrée dans la timeline de l'incident."""
    r = await get_redis()
    raw = await r.get(f"{INCIDENT_PREFIX}{incident_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} introuvable")

    inc = Incident(**json.loads(raw))
    inc.timeline.append(TimelineEntry(
        action="Note ajoutée",
        author=note.author,
        details=note.note,
    ))
    inc.updated_at = datetime.utcnow()
    await r.set(f"{INCIDENT_PREFIX}{inc.id}", inc.model_dump_json())
    return {"message": "Note ajoutée", "incident_id": incident_id}


@router.post("/{incident_id}/alerts/{alert_id}", summary="Lier une alerte")
async def link_alert(incident_id: str, alert_id: str):
    """Associe une alerte à un incident existant."""
    r = await get_redis()
    raw = await r.get(f"{INCIDENT_PREFIX}{incident_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} introuvable")

    inc = Incident(**json.loads(raw))
    if alert_id not in inc.alert_ids:
        inc.alert_ids.append(alert_id)
        inc.updated_at = datetime.utcnow()
        await r.set(f"{INCIDENT_PREFIX}{inc.id}", inc.model_dump_json())

        # Lier dans OpenSearch
        from api.services.opensearch import OpenSearchClient
        await OpenSearchClient().update_alert(alert_id, {"incident_id": incident_id})

    return {"message": "Alerte liée à l'incident", "incident_id": incident_id, "alert_id": alert_id}


@router.delete("/{incident_id}", summary="Supprimer un incident")
async def delete_incident(incident_id: str):
    """Supprime un incident (irréversible)."""
    r = await get_redis()
    deleted = await r.delete(f"{INCIDENT_PREFIX}{incident_id}")
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} introuvable")
    await r.lrem(INCIDENT_LIST_KEY, 0, incident_id)
    return {"message": "Incident supprimé", "incident_id": incident_id}
