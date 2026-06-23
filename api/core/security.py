"""
Sécurité — JWT, hachage mots de passe, rôles
"""
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api.core.config import settings

# ----------------------------------------------------------
# Hachage mot de passe
# ----------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# ----------------------------------------------------------
# Rôles utilisateur
# ----------------------------------------------------------
class Role(str, Enum):
    ADMIN      = "admin"      # Tout accès + gestion utilisateurs
    ANALYST    = "analyst"    # Alertes, incidents, playbooks
    TRIAGER    = "triager"    # Triage des rapports VDP / bug-bounty
    RESEARCHER = "researcher" # Soumission de rapports VDP
    VIEWER     = "viewer"     # Lecture seule

ROLE_PERMISSIONS = {
    Role.ADMIN:      ["read", "write", "delete", "admin", "triage"],
    Role.ANALYST:    ["read", "write", "triage"],
    Role.TRIAGER:    ["read", "triage"],
    Role.RESEARCHER: ["read", "submit"],
    Role.VIEWER:     ["read"],
}

# ----------------------------------------------------------
# JWT
# ----------------------------------------------------------
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE  = timedelta(minutes=30)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)

def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + ACCESS_TOKEN_EXPIRE
    payload["type"] = "access"
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + REFRESH_TOKEN_EXPIRE
    payload["type"] = "refresh"
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ----------------------------------------------------------
# Dépendances FastAPI
# ----------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
):
    """Extrait et valide le token JWT depuis le header Authorization ou cookie."""
    token = None

    # 1. Header Authorization: Bearer <token>
    if credentials:
        token = credentials.credentials

    # 2. Cookie httpOnly (fallback)
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token de type incorrect")

    username = payload.get("sub")
    role     = payload.get("role", Role.VIEWER)
    if not username:
        raise HTTPException(status_code=401, detail="Token sans sujet")

    return {"username": username, "role": role}


def require_role(*roles: Role):
    """Dépendance : vérifie que l'utilisateur a l'un des rôles requis."""
    async def _checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé — rôles requis : {[r.value for r in roles]}",
            )
        return current_user
    return _checker

require_analyst = require_role(Role.ADMIN, Role.ANALYST)
require_admin   = require_role(Role.ADMIN)
require_triager = require_role(Role.ADMIN, Role.ANALYST, Role.TRIAGER)
