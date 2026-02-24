"""
Service d'audit — journalise toutes les actions sensibles
"""
import json
import logging
from datetime import datetime
import redis.asyncio as aioredis
from api.core.config import settings

logger = logging.getLogger("audit")
AUDIT_KEY = "audit:log"
MAX_ENTRIES = 10000


async def log_action(action: str, username: str, ip: str = "?", details: dict | None = None):
    """Enregistre une action dans le journal d'audit Redis + logs structurés."""
    entry = {
        "ts":       datetime.utcnow().isoformat() + "Z",
        "action":   action,
        "user":     username,
        "ip":       ip,
        "details":  details or {},
    }
    logger.info("[AUDIT] %s", json.dumps(entry))

    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
        await r.lpush(AUDIT_KEY, json.dumps(entry))
        await r.ltrim(AUDIT_KEY, 0, MAX_ENTRIES - 1)
    except Exception as e:
        logger.warning("Erreur écriture audit Redis: %s", e)


async def get_audit_log(limit: int = 100) -> list:
    try:
        r = aioredis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )
        entries = await r.lrange(AUDIT_KEY, 0, limit - 1)
        return [json.loads(e) for e in entries]
    except Exception:
        return []
