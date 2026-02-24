"""
Service de déduplication — Évite les alertes en double
Utilise Redis comme backend de cache distribué.
"""
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional
import redis.asyncio as redis

from api.core.config import settings

logger = logging.getLogger(__name__)

# Cache Redis pour la déduplication
_redis_client: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
    return _redis_client


def compute_signature(alert: dict) -> str:
    """
    Génère une signature unique pour une alerte.
    Même règle + même agent + même IP source = même signature.
    """
    key_parts = [
        str(alert.get("rule", {}).get("id", "")),
        str(alert.get("agent", {}).get("id", "")),
        str(alert.get("data", {}).get("srcip", "")),
    ]
    raw = "|".join(key_parts)
    return hashlib.sha256(raw.encode()).hexdigest()


async def is_duplicate(alert: dict, window_minutes: Optional[int] = None) -> bool:
    """
    Vérifie si une alerte est un doublon.
    Returns True si l'alerte a déjà été vue dans la fenêtre de temps.
    """
    window = window_minutes or settings.DEDUP_WINDOW_MINUTES
    sig = compute_signature(alert)
    redis_key = f"dedup:{sig}"

    try:
        r = await get_redis()
        exists = await r.exists(redis_key)
        if exists:
            # Mise à jour du compteur de doublons
            await r.incr(f"dedup_count:{sig}")
            return True

        # Marquer comme vu avec TTL
        await r.setex(redis_key, window * 60, "1")
        return False

    except Exception as e:
        logger.warning("Redis indisponible pour déduplication, bypass: %s", e)
        return False  # En cas d'erreur Redis, on laisse passer


async def mark_seen(alert: dict, window_minutes: Optional[int] = None) -> None:
    """Marque une alerte comme vue (pour mise à jour manuelle)."""
    window = window_minutes or settings.DEDUP_WINDOW_MINUTES
    sig = compute_signature(alert)
    try:
        r = await get_redis()
        await r.setex(f"dedup:{sig}", window * 60, "1")
    except Exception as e:
        logger.warning("Erreur mark_seen Redis: %s", e)


async def cleanup_dedup_cache() -> None:
    """
    Tâche planifiée : nettoyage des clés expirées.
    Redis gère le TTL automatiquement, mais on peut logguer des stats.
    """
    try:
        r = await get_redis()
        info = await r.info("keyspace")
        logger.info("Redis keyspace stats: %s", info)
    except Exception as e:
        logger.error("Erreur cleanup_dedup_cache: %s", e)
