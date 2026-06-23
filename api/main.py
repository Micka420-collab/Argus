"""
SOC Platform — Point d'entrée FastAPI
Inclut : Auth JWT, Rate limiting, Security headers, Audit log
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.core.config import settings
from api.core.scheduler import start_scheduler, stop_scheduler
from api.routers import alerts, incidents, assets, rules, playbooks
from api.routers import auth as auth_router
from api.routers import investigation as investigation_router
from api.routers import crypto as crypto_router
from api.routers import ai as ai_router
from api.services.alerting import AlertEngine
from api.services.users import ensure_default_admin
from api.middleware.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    AuditMiddleware,
)

# Logging structuré
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Instance globale du moteur d'alerting
_alert_engine: AlertEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    global _alert_engine

    logger.info("Démarrage SOC Platform v%s (%s)", settings.APP_VERSION, settings.ENVIRONMENT)

    # Créer l'administrateur par défaut si nécessaire
    await ensure_default_admin()

    # Démarrer le scheduler (tâches de fond)
    await start_scheduler()

    # Démarrer le moteur d'alerting
    _alert_engine = AlertEngine()
    await _alert_engine.start()

    logger.info("SOC Platform démarrée avec succès")

    yield  # Application en cours d'exécution

    # Arrêt propre
    logger.info("Arrêt SOC Platform...")
    if _alert_engine:
        await _alert_engine.stop()
    await stop_scheduler()
    logger.info("SOC Platform arrêtée")


# ----------------------------------------------------------
# Création de l'application FastAPI
# ----------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Plateforme SOC — Alerting, Corrélation, Ticketing, Playbooks",
    docs_url="/docs" if settings.DEBUG else None,  # Swagger désactivé en prod
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ----------------------------------------------------------
# Middlewares (ordre important : dernier ajouté = premier exécuté)
# ----------------------------------------------------------

# 1. CORS (doit être en premier pour les preflight)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 2. Security headers sur toutes les réponses
app.add_middleware(SecurityHeadersMiddleware)

# 3. Rate limiting par IP
app.add_middleware(RateLimitMiddleware)

# 4. Audit log des mutations (POST/PATCH/DELETE)
app.add_middleware(AuditMiddleware)


# ----------------------------------------------------------
# Routes
# ----------------------------------------------------------
app.include_router(auth_router.router,          prefix="/api/v1/auth",        tags=["Auth"])
app.include_router(alerts.router,               prefix="/api/v1/alerts",      tags=["Alertes"])
app.include_router(incidents.router,            prefix="/api/v1/incidents",   tags=["Incidents"])
app.include_router(assets.router,               prefix="/api/v1/assets",      tags=["Assets"])
app.include_router(rules.router,                prefix="/api/v1/rules",       tags=["Règles"])
app.include_router(playbooks.router,            prefix="/api/v1/playbooks",   tags=["Playbooks"])
app.include_router(investigation_router.router, prefix="/api/v1/investigate", tags=["Investigation OSINT"])
app.include_router(crypto_router.router,         prefix="/api/v1/crypto",      tags=["Post-Quantum"])
app.include_router(ai_router.router,             prefix="/api/v1/ai",          tags=["Analyste IA"])


# ----------------------------------------------------------
# Endpoints utilitaires
# ----------------------------------------------------------
@app.get("/health", tags=["Système"], summary="Health check")
async def health():
    """Vérification de l'état de l'application (pas d'auth requise)."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


@app.get("/api/v1/status", tags=["Système"], summary="Statut des services")
async def status():
    """Statut de tous les services connectés."""
    from api.services.opensearch import OpenSearchClient
    from api.services.deduplication import get_redis

    opensearch_ok = False
    redis_ok = False

    try:
        os_client = OpenSearchClient()
        client = await os_client.get_client()
        await client.info()
        opensearch_ok = True
    except Exception as e:
        logger.warning("OpenSearch non disponible: %s", e)

    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception as e:
        logger.warning("Redis non disponible: %s", e)

    return {
        "opensearch":   "ok" if opensearch_ok else "error",
        "redis":        "ok" if redis_ok else "error",
        "alert_engine": "running" if _alert_engine and _alert_engine._running else "stopped",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Erreur non gérée: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur"},
    )
