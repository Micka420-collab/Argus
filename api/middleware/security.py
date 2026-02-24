"""
Middleware de sécurité FastAPI
- Rate limiting par IP (Redis)
- Security headers (HSTS, CSP, X-Frame-Options...)
- Logging des requêtes
"""
import time
import logging
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Compteurs en mémoire (fallback si Redis absent)
_counters: dict = defaultdict(list)

# Routes exclues du rate limiting strict
RATE_LIMIT_BYPASS = {"/health", "/api/v1/auth/refresh"}

# Limites par route
RATE_LIMITS = {
    "/api/v1/auth/login": (10, 60),   # 10 req/60s — anti-bruteforce login
    "default":            (200, 60),  # 200 req/60s par défaut
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injecte les headers de sécurité sur toutes les réponses."""

    SECURITY_HEADERS = {
        "X-Content-Type-Options":    "nosniff",
        "X-Frame-Options":           "DENY",
        "X-XSS-Protection":          "1; mode=block",
        "Referrer-Policy":           "strict-origin-when-cross-origin",
        "Permissions-Policy":        "geolocation=(), microphone=(), camera=()",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' wss:; "
            "frame-ancestors 'none';"
        ),
    }

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for header, value in self.SECURITY_HEADERS.items():
            response.headers[header] = value
        # Supprimer le header qui expose la technologie
        response.headers.pop("server", None)
        response.headers.pop("x-powered-by", None)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting par IP avec compteurs Redis."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in RATE_LIMIT_BYPASS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        limit, window = RATE_LIMITS.get(path, RATE_LIMITS["default"])

        if not await self._check_rate_limit(client_ip, path, limit, window):
            logger.warning("Rate limit atteint: %s → %s", client_ip, path)
            return Response(
                content='{"detail":"Trop de requêtes — réessayer dans un moment"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(window), "X-RateLimit-Limit": str(limit)},
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        # Respecter X-Forwarded-For si derrière Nginx
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _check_rate_limit(self, ip: str, path: str, limit: int, window: int) -> bool:
        """Vérifie le rate limit. Retourne True si la requête est autorisée."""
        try:
            from api.services.deduplication import get_redis
            r = await get_redis()
            key = f"rl:{ip}:{path}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window)
            return count <= limit
        except Exception:
            # Si Redis indisponible, utiliser compteur en mémoire
            now = time.time()
            key = f"{ip}:{path}"
            _counters[key] = [t for t in _counters[key] if now - t < window]
            _counters[key].append(now)
            return len(_counters[key]) <= limit


class AuditMiddleware(BaseHTTPMiddleware):
    """Log structuré de toutes les actions mutantes (POST, PATCH, DELETE)."""

    LOGGED_METHODS = {"POST", "PATCH", "DELETE", "PUT"}
    SKIP_PATHS = {"/health", "/api/v1/auth/refresh", "/api/v1/alerts/ws"}

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000)

        if request.method in self.LOGGED_METHODS and request.url.path not in self.SKIP_PATHS:
            user = getattr(request.state, "user", {})
            logger.info(
                "API %s %s → %d (%dms) user=%s ip=%s",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                user.get("username", "anonymous"),
                request.headers.get("X-Forwarded-For", request.client.host if request.client else "?"),
            )

        return response
