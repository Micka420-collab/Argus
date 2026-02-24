"""
Gestion des utilisateurs — stockage Redis
Crée un compte admin par défaut au premier démarrage.
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List

import redis.asyncio as aioredis

from api.core.config import settings
from api.core.security import hash_password, verify_password, Role
from api.models.user import UserCreate

logger = logging.getLogger(__name__)

USER_PREFIX = "user:"
USER_INDEX  = "users:by_username"   # Hash Redis : username → id


async def _redis() -> aioredis.Redis:
    return aioredis.from_url(
        settings.REDIS_URL,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True,
    )


async def get_user_by_username(username: str) -> Optional[dict]:
    r = await _redis()
    user_id = await r.hget(USER_INDEX, username)
    if not user_id:
        return None
    raw = await r.get(f"{USER_PREFIX}{user_id}")
    return json.loads(raw) if raw else None


async def get_user_by_id(user_id: str) -> Optional[dict]:
    r = await _redis()
    raw = await r.get(f"{USER_PREFIX}{user_id}")
    return json.loads(raw) if raw else None


async def list_users() -> List[dict]:
    r = await _redis()
    usernames = await r.hkeys(USER_INDEX)
    users = []
    for uname in usernames:
        user = await get_user_by_username(uname)
        if user:
            user_copy = dict(user)
            user_copy.pop("password_hash", None)
            users.append(user_copy)
    return users


async def create_user(user_in: UserCreate) -> dict:
    r = await _redis()

    # Vérifier unicité
    if await r.hget(USER_INDEX, user_in.username):
        raise ValueError(f"L'utilisateur '{user_in.username}' existe déjà")

    user_id = str(uuid.uuid4())
    user_data = {
        "id":            user_id,
        "username":      user_in.username,
        "email":         user_in.email or "",
        "full_name":     user_in.full_name or "",
        "role":          user_in.role.value,
        "is_active":     True,
        "password_hash": hash_password(user_in.password),
        "created_at":    datetime.utcnow().isoformat(),
        "last_login":    None,
    }

    await r.set(f"{USER_PREFIX}{user_id}", json.dumps(user_data))
    await r.hset(USER_INDEX, user_in.username, user_id)

    logger.info("Utilisateur créé : %s (rôle: %s)", user_in.username, user_in.role)
    user_data.pop("password_hash")
    return user_data


async def authenticate(username: str, password: str) -> Optional[dict]:
    """Authentifie un utilisateur. Retourne ses données sans le hash."""
    user = await get_user_by_username(username)
    if not user:
        return None
    if not user.get("is_active", True):
        return None
    if not verify_password(password, user.get("password_hash", "")):
        return None

    # Mettre à jour last_login
    r = await _redis()
    user["last_login"] = datetime.utcnow().isoformat()
    await r.set(f"{USER_PREFIX}{user['id']}", json.dumps(user))

    result = dict(user)
    result.pop("password_hash", None)
    return result


async def update_user(user_id: str, updates: dict) -> Optional[dict]:
    r = await _redis()
    raw = await r.get(f"{USER_PREFIX}{user_id}")
    if not raw:
        return None
    user = json.loads(raw)
    if "password" in updates:
        user["password_hash"] = hash_password(updates.pop("password"))
    user.update(updates)
    await r.set(f"{USER_PREFIX}{user_id}", json.dumps(user))
    result = dict(user)
    result.pop("password_hash", None)
    return result


async def delete_user(user_id: str) -> bool:
    r = await _redis()
    raw = await r.get(f"{USER_PREFIX}{user_id}")
    if not raw:
        return False
    user = json.loads(raw)
    await r.delete(f"{USER_PREFIX}{user_id}")
    await r.hdel(USER_INDEX, user["username"])
    return True


async def ensure_default_admin():
    """
    Crée le compte admin par défaut si aucun utilisateur n'existe.
    Mot de passe dans les logs au premier démarrage.
    """
    r = await _redis()
    count = await r.hlen(USER_INDEX)
    if count > 0:
        return

    default_password = "Admin@SOC2024!"
    await create_user(UserCreate(
        username="admin",
        password=default_password,
        full_name="Administrateur SOC",
        role=Role.ADMIN,
    ))
    logger.warning("=" * 60)
    logger.warning("COMPTE ADMIN PAR DÉFAUT CRÉÉ")
    logger.warning("  Username : admin")
    logger.warning("  Password : %s", default_password)
    logger.warning("  → CHANGER CE MOT DE PASSE IMMÉDIATEMENT !")
    logger.warning("=" * 60)
