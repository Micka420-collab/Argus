"""
SOC Platform — Client API Wazuh Manager
=======================================
Liste les machines (agents Wazuh) présentes sur le réseau et fournit la
commande d'enrôlement pour en connecter une nouvelle.

L'API Wazuh (port 55000) utilise un certificat auto-signé et un JWT court :
on s'authentifie en Basic Auth puis on réutilise le token ~15 min (cache).
Tout est défensif : si le manager est indisponible, on renvoie une liste vide
plutôt que de planter l'interface.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from api.core.config import settings

logger = logging.getLogger(__name__)

# Cache du token JWT Wazuh (évite de se ré-authentifier à chaque appel)
_token: str | None = None
_token_exp: float = 0.0


async def _get_token(client: httpx.AsyncClient) -> str | None:
    global _token, _token_exp
    if _token and time.monotonic() < _token_exp:
        return _token
    try:
        r = await client.get(
            f"{settings.WAZUH_API_URL}/security/user/authenticate",
            auth=(settings.WAZUH_API_USER, settings.WAZUH_API_PASSWORD),
        )
        r.raise_for_status()
        _token = r.json()["data"]["token"]
        _token_exp = time.monotonic() + 800  # ~13 min de marge
        return _token
    except Exception as e:
        logger.warning("Authentification API Wazuh impossible : %s", e)
        return None


def _normalize_agent(a: dict[str, Any]) -> dict[str, Any]:
    os_info = a.get("os", {}) or {}
    return {
        "id":         a.get("id", ""),
        "name":       a.get("name", ""),
        "ip":         a.get("ip", "") or a.get("registerIP", ""),
        "status":     a.get("status", "unknown"),       # active | disconnected | never_connected | pending
        "os":         os_info.get("name", "") or os_info.get("platform", ""),
        "os_version": os_info.get("version", ""),
        "version":    a.get("version", ""),
        "group":      ", ".join(a.get("group", []) or []),
        "last_seen":  a.get("lastKeepAlive", ""),
        "registered": a.get("dateAdd", ""),
        "node":       a.get("node_name", ""),
    }


async def list_agents() -> dict[str, Any]:
    """
    Renvoie la liste des machines surveillées (agents Wazuh).
    Forme : {"available": bool, "agents": [...], "summary": {...}, "error": str|None}
    """
    if not settings.WAZUH_API_PASSWORD:
        return {"available": False, "agents": [], "summary": {},
                "error": "API Wazuh non configurée (WAZUH_API_PASSWORD vide)."}

    try:
        async with httpx.AsyncClient(verify=False, timeout=8) as client:
            token = await _get_token(client)
            if not token:
                return {"available": False, "agents": [], "summary": {},
                        "error": "Manager Wazuh injoignable ou identifiants invalides."}
            r = await client.get(
                f"{settings.WAZUH_API_URL}/agents",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": 500, "sort": "-lastKeepAlive"},
            )
            r.raise_for_status()
            items = r.json().get("data", {}).get("affected_items", [])
    except Exception as e:
        logger.warning("Liste des agents Wazuh indisponible : %s", e)
        return {"available": False, "agents": [], "summary": {}, "error": str(e)}

    agents = [_normalize_agent(a) for a in items]
    summary = {
        "total":            len(agents),
        "active":           sum(1 for a in agents if a["status"] == "active"),
        "disconnected":     sum(1 for a in agents if a["status"] == "disconnected"),
        "never_connected":  sum(1 for a in agents if a["status"] == "never_connected"),
        "pending":          sum(1 for a in agents if a["status"] == "pending"),
    }
    return {"available": True, "agents": agents, "summary": summary, "error": None}


def enroll_info() -> dict[str, Any]:
    """
    Renvoie tout ce qu'il faut pour CONNECTER une machine au SOC :
    l'adresse du manager + les commandes d'installation de l'agent Wazuh
    (Linux & Windows). `manager_host` doit être l'IP/DNS joignable par l'endpoint.
    """
    manager = settings.SOC_DOMAIN or "ADRESSE_DU_SERVEUR"
    return {
        "manager_host": manager,
        "enrollment_port": 1515,
        "agent_port": 1514,
        "linux": (
            "curl -so wazuh-agent.deb "
            "https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.7.3-1_amd64.deb "
            f"&& sudo WAZUH_MANAGER='{manager}' dpkg -i ./wazuh-agent.deb "
            "&& sudo systemctl enable --now wazuh-agent"
        ),
        "windows": (
            "Invoke-WebRequest -Uri https://packages.wazuh.com/4.x/windows/wazuh-agent-4.7.3-1.msi "
            "-OutFile $env:tmp\\wazuh-agent.msi; "
            f"msiexec.exe /i $env:tmp\\wazuh-agent.msi /q WAZUH_MANAGER='{manager}'; "
            "NET START WazuhSvc"
        ),
        "note": (
            "Remplacez l'adresse du manager si l'endpoint n'est pas sur le même "
            "réseau. Ouvrez les ports 1514/udp et 1515/tcp du serveur SOC vers "
            "le sous-réseau des machines à surveiller."
        ),
    }
