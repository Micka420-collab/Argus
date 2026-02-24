"""
Router — Alertes
CRUD + WebSocket temps réel
"""
import json
import logging
from datetime import datetime
from typing import Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import JSONResponse
import redis.asyncio as aioredis

from api.models.alert import Alert, AlertUpdate, AlertListResponse, AlertSeverity, AlertStatus
from api.services.opensearch import OpenSearchClient
from api.core.config import settings
from api.core.security import decode_token

# ---------------------------------------------------------------------------
# Cache Redis pour les stats du dashboard (TTL 5 minutes)
# ---------------------------------------------------------------------------
_redis: aioredis.Redis | None = None

async def _get_redis() -> aioredis.Redis | None:
    global _redis
    if _redis is None:
        try:
            _redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
            )
            await _redis.ping()
        except Exception:
            _redis = None
    return _redis

router = APIRouter()
logger = logging.getLogger(__name__)

# Connexions WebSocket actives
_ws_connections: Set[WebSocket] = set()


# ----------------------------------------------------------
# WebSocket — Alertes temps réel
# ----------------------------------------------------------

@router.websocket("/ws")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint — Alertes temps réel.
    Auth : token JWT transmis via query param ?token=<access_token>
    (les WebSockets ne supportent pas les headers Authorization standards).
    """
    # ── Authentification ──────────────────────────────────────────────────
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token manquant")
        return
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4003, reason="Token invalide ou expiré")
        return

    username = payload.get("sub", "inconnu")
    await websocket.accept()
    _ws_connections.add(websocket)
    logger.info("WS connecté: %s — clients actifs: %d", username, len(_ws_connections))
    try:
        while True:
            # Keep-alive : attendre un ping du client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        _ws_connections.discard(websocket)
        logger.info("Client WebSocket déconnecté. Total: %d", len(_ws_connections))
    except Exception as e:
        _ws_connections.discard(websocket)
        logger.error("Erreur WebSocket: %s", e)


async def broadcast_alert(alert: dict):
    """
    Diffuse une alerte à tous les clients WebSocket connectés.
    Appelé par l'AlertEngine.
    """
    if not _ws_connections:
        return

    message = json.dumps(alert, default=str)
    dead: Set[WebSocket] = set()

    for ws in list(_ws_connections):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)

    _ws_connections -= dead


# ----------------------------------------------------------
# REST API
# ----------------------------------------------------------

@router.get("", response_model=AlertListResponse, summary="Liste des alertes")
async def list_alerts(
    q: Optional[str] = Query(None, description="Recherche texte libre"),
    severity: Optional[str] = Query(None, description="low|medium|high|critical"),
    status: Optional[str] = Query(None, description="new|in_progress|resolved|false_positive"),
    agent_name: Optional[str] = Query(None, description="Filtrer par agent/machine"),
    mitre_id: Optional[str] = Query(None, description="Filtrer par MITRE ATT&CK ID"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
):
    """Recherche et liste des alertes avec filtres avancés."""
    os = OpenSearchClient()
    result = await os.search_alerts(
        q=q,
        severity=severity,
        status=status,
        agent_name=agent_name,
        mitre_id=mitre_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        per_page=per_page,
    )
    return result


@router.get("/stats", summary="Statistiques du dashboard")
async def get_stats(
    period_hours: int = Query(24, ge=1, le=720, description="Période en heures"),
):
    """
    Statistiques agrégées pour le dashboard.
    Résultat mis en cache Redis 5 minutes pour éviter de surcharger OpenSearch.
    """
    cache_key = f"soc:stats:{period_hours}h"
    r = await _get_redis()

    # Tentative lecture cache
    if r:
        try:
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # Calcul depuis OpenSearch
    os_client = OpenSearchClient()
    result = await os_client.get_stats(period_hours=period_hours)

    # Écriture en cache (TTL 5 min)
    if r:
        try:
            await r.setex(cache_key, 300, json.dumps(result, default=str))
        except Exception:
            pass

    return result


@router.get("/{alert_id}", summary="Détail d'une alerte")
async def get_alert(alert_id: str):
    """Récupère le détail complet d'une alerte."""
    os = OpenSearchClient()
    alert = await os.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alerte {alert_id} introuvable")
    return alert


@router.patch("/{alert_id}", summary="Mettre à jour une alerte")
async def update_alert(alert_id: str, update: AlertUpdate):
    """Met à jour le statut, les notes ou l'assignation d'une alerte."""
    os = OpenSearchClient()

    # Vérifier que l'alerte existe
    existing = await os.get_alert(alert_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Alerte {alert_id} introuvable")

    # Construire le document de mise à jour
    fields = {k: v for k, v in update.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="Aucun champ à mettre à jour")

    success = await os.update_alert(alert_id, fields)
    if not success:
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour")

    return {"message": "Alerte mise à jour", "alert_id": alert_id, "updated": fields}


@router.post("/{alert_id}/enrich", summary="Lancer l'enrichissement")
async def enrich_alert(alert_id: str):
    """Déclenche manuellement l'enrichissement d'une alerte."""
    import asyncio
    from api.services.enrichment import EnrichmentService

    os = OpenSearchClient()
    alert = await os.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alerte {alert_id} introuvable")

    src_ip = alert.get("data", {}).get("srcip") or alert.get("src_ip")
    if not src_ip:
        raise HTTPException(status_code=400, detail="Pas d'IP source dans cette alerte")

    enricher = EnrichmentService()
    asyncio.create_task(enricher.enrich_ip(src_ip, alert_id))

    return {"message": f"Enrichissement lancé pour {src_ip}", "alert_id": alert_id}


@router.post("/{alert_id}/false-positive", summary="Marquer faux positif")
async def mark_false_positive(alert_id: str, reason: str = ""):
    """Marque une alerte comme faux positif."""
    os = OpenSearchClient()
    success = await os.update_alert(alert_id, {
        "status": AlertStatus.FALSE_POSITIVE,
        "notes": f"[FAUX POSITIF] {reason}",
    })
    if not success:
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour")
    return {"message": "Alerte marquée comme faux positif", "alert_id": alert_id}


@router.get("/ws/stats", summary="Stats WebSocket")
async def ws_stats():
    """Nombre de clients WebSocket connectés."""
    return {"connected_clients": len(_ws_connections)}
