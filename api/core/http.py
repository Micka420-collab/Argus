"""
SOC Platform — Client HTTP sortant partagé
==========================================

Toutes les requêtes OSINT / threat-intel / LLM doivent passer par ce client
afin que l'égress soit :
  - centralisé (timeouts, headers, retries cohérents)
  - optionnellement anonymisé (Tor / proxy multi-hop — pilier « Snowpack »)

Quand `OUTBOUND_PROXY` est défini (ex. socks5://anon-gateway:9050), toutes les
recherches OSINT sortent par ce tunnel. Cela évite que l'IP réelle du SOC soit
« marquée » par les fournisseurs de réputation et masque quelles IPs sont
investiguées.

Nécessite `httpx[socks]` pour le support SOCKS5 (Tor). Sans proxy configuré,
le comportement est identique à un `httpx.AsyncClient` classique.
"""
from __future__ import annotations

import logging

import httpx

from api.core.config import settings

logger = logging.getLogger(__name__)

# User-Agent neutre — ne révèle pas qu'il s'agit d'un SOC
_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ArgusSOC/3.0; +https://argus.local)",
    "Accept": "application/json",
}


def get_http_client(timeout: float = 8.0, **kwargs) -> httpx.AsyncClient:
    """
    Retourne un `httpx.AsyncClient` configuré pour l'égress sortant.

    - `OUTBOUND_PROXY` + `OSINT_ANON=true` → trafic routé via le proxy (Tor/VPN).
    - `follow_redirects=True` par défaut (RDAP renvoie souvent des 3xx).
    """
    opts: dict = {
        "timeout": timeout,
        "follow_redirects": True,
        "headers": {**_DEFAULT_HEADERS, **kwargs.pop("headers", {})},
    }

    proxy = settings.OUTBOUND_PROXY if settings.OSINT_ANON else None
    if proxy:
        # httpx >= 0.26 : argument `proxy` (str unique). Nécessite httpx[socks]
        # pour les schémas socks5://.
        try:
            opts["proxy"] = proxy
        except Exception:  # pragma: no cover - défensif
            logger.warning("Proxy sortant ignoré (httpx[socks] manquant ?) : %s", proxy)

    opts.update(kwargs)
    return httpx.AsyncClient(**opts)


async def renew_tor_identity() -> bool:
    """
    Demande un nouveau circuit Tor (rotation d'IP de sortie) via le port de
    contrôle, si configuré. Best-effort : retourne False silencieusement sinon.
    """
    ctrl = settings.TOR_CONTROL_URL
    if not ctrl:
        return False
    try:
        # Le control port Tor parle un protocole texte ; on délègue à un petit
        # endpoint HTTP exposé par anon-gateway (signal NEWNYM).
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(ctrl)
            return r.status_code < 400
    except Exception as e:
        logger.warning("Rotation identité Tor impossible : %s", e)
        return False
