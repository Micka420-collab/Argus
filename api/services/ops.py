"""
SOC Platform — Pilotage des opérations serveur (update / restart)
=================================================================
soc-api ne possède PAS l'accès Docker (par sécurité : conteneur non-root, sans
socket Docker). Il dépose simplement une commande dans une file Redis ; un
conteneur dédié privilégié (« argus-ops ») la consomme et exécute git pull /
docker compose. Ce découplage garde l'API non privilégiée.
"""
from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as aioredis

from api.core.config import settings

logger = logging.getLogger(__name__)

QUEUE_KEY  = "argus:ops:queue"
STATUS_KEY = "argus:ops:status"
ALLOWED    = {"update", "restart"}

_redis: Optional[aioredis.Redis] = None


async def _get_redis() -> Optional[aioredis.Redis]:
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
        except Exception as e:
            logger.warning("Redis indisponible pour ops : %s", e)
            _redis = None
    return _redis


async def enqueue(command: str) -> bool:
    """Place une commande (`update`/`restart`) dans la file de l'agent ops."""
    if command not in ALLOWED:
        raise ValueError(f"Commande inconnue : {command}")
    r = await _get_redis()
    if not r:
        return False
    await r.rpush(QUEUE_KEY, command)
    await r.set(STATUS_KEY, f"queued:{command}")
    logger.info("Commande ops mise en file : %s", command)
    return True


async def status() -> dict:
    """État de la dernière opération (queued / running / done / error)."""
    r = await _get_redis()
    if not r:
        return {"state": "unknown", "detail": "Redis indisponible"}
    raw = await r.get(STATUS_KEY)
    if not raw:
        return {"state": "idle", "detail": ""}
    state, _, detail = raw.partition(":")
    return {"state": state, "detail": detail}
