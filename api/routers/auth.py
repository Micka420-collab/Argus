"""
Router — Authentification
Login · Logout · Refresh · Profil · Gestion utilisateurs
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Response, Request

from api.core.security import (
    create_access_token, create_refresh_token, decode_token,
    get_current_user, require_admin, Role,
)
from api.models.user import LoginRequest, TokenResponse, UserCreate, UserUpdate
from api.services import users as user_svc
from api.services.audit import log_action

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=TokenResponse, summary="Connexion")
async def login(request: Request, body: LoginRequest, response: Response):
    user = await user_svc.authenticate(body.username, body.password)
    if not user:
        await log_action("auth_failure", body.username, request.client.host if request.client else "?")
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    access_token  = create_access_token({"sub": user["username"], "role": user["role"]})
    refresh_token = create_refresh_token({"sub": user["username"], "role": user["role"]})

    await log_action("auth_success", user["username"], request.client.host if request.client else "?")
    logger.info("Connexion réussie : %s (rôle: %s)", user["username"], user["role"])

    # Cookie httpOnly pour sécurité maximale
    response.set_cookie(
        key="access_token",  value=access_token,
        httponly=True, secure=True, samesite="strict", max_age=1800,
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=True, samesite="strict", max_age=604800,
        path="/api/v1/auth/refresh",
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"username": user["username"], "role": user["role"], "full_name": user.get("full_name","")},
    )


@router.post("/logout", summary="Déconnexion")
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Déconnecté"}


@router.post("/refresh", summary="Renouveler le token")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token") or (
        (await request.json()).get("refresh_token") if request.headers.get("content-type") == "application/json" else None
    )
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token manquant")

    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token invalide")

    new_access = create_access_token({"sub": payload["sub"], "role": payload["role"]})
    response.set_cookie(
        key="access_token", value=new_access,
        httponly=True, secure=True, samesite="strict", max_age=1800,
    )
    return {"access_token": new_access, "token_type": "bearer", "expires_in": 1800}


@router.get("/me", summary="Profil courant")
async def me(current_user: dict = Depends(get_current_user)):
    user = await user_svc.get_user_by_username(current_user["username"])
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.pop("password_hash", None)
    return user


# ----------------------------------------------------------
# Gestion des utilisateurs (admin uniquement)
# ----------------------------------------------------------
@router.get("/users", summary="Liste utilisateurs", dependencies=[Depends(require_admin)])
async def list_users():
    return await user_svc.list_users()


@router.post("/users", status_code=201, summary="Créer utilisateur", dependencies=[Depends(require_admin)])
async def create_user(user_in: UserCreate):
    try:
        return await user_svc.create_user(user_in)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/users/{user_id}", summary="Modifier utilisateur", dependencies=[Depends(require_admin)])
async def update_user(user_id: str, update: UserUpdate):
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    if "role" in updates:
        updates["role"] = updates["role"].value
    result = await user_svc.update_user(user_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return result


@router.delete("/users/{user_id}", summary="Supprimer utilisateur", dependencies=[Depends(require_admin)])
async def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    user = await user_svc.get_user_by_username(current_user["username"])
    if user and user["id"] == user_id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte")
    if not await user_svc.delete_user(user_id):
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return {"message": "Utilisateur supprimé"}
