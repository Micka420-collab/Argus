"""
Router — Assets / Inventaire
Gestion des machines surveillées.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
import redis.asyncio as aioredis

from api.models.asset import Asset, AssetCreate, AssetUpdate
from api.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

ASSET_PREFIX = "asset:"
ASSET_LIST_KEY = "assets:list"


async def get_redis() -> aioredis.Redis:
    return aioredis.from_url(
        settings.REDIS_URL,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True,
    )


@router.get("", summary="Liste des assets")
async def list_assets(
    type: Optional[str] = None,
    criticality: Optional[str] = None,
    department: Optional[str] = None,
    in_maintenance: Optional[bool] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
):
    r = await get_redis()
    asset_ids = await r.lrange(ASSET_LIST_KEY, 0, -1)

    assets = []
    for aid in asset_ids:
        raw = await r.get(f"{ASSET_PREFIX}{aid}")
        if raw:
            asset = Asset(**json.loads(raw))
            if type and asset.type != type:
                continue
            if criticality and asset.criticality != criticality:
                continue
            if department and asset.department != department:
                continue
            if in_maintenance is not None and asset.in_maintenance != in_maintenance:
                continue
            assets.append(asset)

    total = len(assets)
    start = (page - 1) * per_page
    items = assets[start: start + per_page]

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [a.model_dump() for a in items],
    }


@router.post("", status_code=201, summary="Ajouter un asset")
async def create_asset(asset_in: AssetCreate):
    r = await get_redis()

    # Vérifier si IP déjà enregistrée
    asset_ids = await r.lrange(ASSET_LIST_KEY, 0, -1)
    for aid in asset_ids:
        raw = await r.get(f"{ASSET_PREFIX}{aid}")
        if raw:
            existing = Asset(**json.loads(raw))
            if existing.ip == asset_in.ip:
                raise HTTPException(
                    status_code=409,
                    detail=f"Un asset avec l'IP {asset_in.ip} existe déjà (ID: {existing.id})",
                )

    asset = Asset(id=str(uuid.uuid4()), **asset_in.model_dump())
    await r.set(f"{ASSET_PREFIX}{asset.id}", asset.model_dump_json())
    await r.lpush(ASSET_LIST_KEY, asset.id)
    return asset


@router.get("/{asset_id}", summary="Détail d'un asset")
async def get_asset(asset_id: str):
    r = await get_redis()
    raw = await r.get(f"{ASSET_PREFIX}{asset_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} introuvable")
    return json.loads(raw)


@router.patch("/{asset_id}", summary="Mettre à jour un asset")
async def update_asset(asset_id: str, update: AssetUpdate):
    r = await get_redis()
    raw = await r.get(f"{ASSET_PREFIX}{asset_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} introuvable")

    asset = Asset(**json.loads(raw))
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    for field, value in update_data.items():
        setattr(asset, field, value)
    asset.updated_at = datetime.utcnow()

    await r.set(f"{ASSET_PREFIX}{asset.id}", asset.model_dump_json())
    return asset


@router.post("/{asset_id}/maintenance", summary="Activer/désactiver la maintenance")
async def toggle_maintenance(
    asset_id: str,
    enable: bool = True,
    until: Optional[datetime] = None,
):
    """
    Active ou désactive le mode maintenance pour un asset.
    En mode maintenance, les alertes de cet asset sont ignorées.
    """
    r = await get_redis()
    raw = await r.get(f"{ASSET_PREFIX}{asset_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} introuvable")

    asset = Asset(**json.loads(raw))
    asset.in_maintenance = enable
    asset.maintenance_until = until
    asset.updated_at = datetime.utcnow()
    await r.set(f"{ASSET_PREFIX}{asset.id}", asset.model_dump_json())

    # Clé Redis pour le moteur d'alerting
    maintenance_key = f"maintenance:{asset.ip}"
    if enable:
        ttl = int((until - datetime.utcnow()).total_seconds()) if until else 86400
        await r.setex(maintenance_key, ttl, "1")
        msg = f"Maintenance activée pour {asset.hostname} ({asset.ip})"
    else:
        await r.delete(maintenance_key)
        msg = f"Maintenance désactivée pour {asset.hostname} ({asset.ip})"

    return {"message": msg, "asset_id": asset_id}


@router.get("/{asset_id}/alerts", summary="Alertes d'un asset")
async def get_asset_alerts(
    asset_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Récupère les dernières alertes associées à un asset."""
    r = await get_redis()
    raw = await r.get(f"{ASSET_PREFIX}{asset_id}")
    if not raw:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} introuvable")

    asset = Asset(**json.loads(raw))
    from api.services.opensearch import OpenSearchClient
    os = OpenSearchClient()
    result = await os.search_alerts(agent_name=asset.hostname, per_page=limit)
    return result


@router.delete("/{asset_id}", summary="Supprimer un asset")
async def delete_asset(asset_id: str):
    r = await get_redis()
    deleted = await r.delete(f"{ASSET_PREFIX}{asset_id}")
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} introuvable")
    await r.lrem(ASSET_LIST_KEY, 0, asset_id)
    return {"message": "Asset supprimé", "asset_id": asset_id}
