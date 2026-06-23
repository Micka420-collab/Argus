"""
SOC Platform — Webhooks sortants (sync tickets : n8n / Slack / Jira / …)
=======================================================================
Émet un événement HTTP POST signé (HMAC-SHA256) vers `WEBHOOK_URL` lors des
moments clés : verdict IA malveillant, rapport VDP accepté, finding KEV.

Best-effort et non bloquant : si `WEBHOOK_URL` n'est pas configuré, no-op.
Trafic interne/utilisateur → n'emprunte PAS l'égress anonymisé (Tor).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

from api.core.config import settings

logger = logging.getLogger(__name__)


async def emit(event: str, data: dict) -> bool:
    """Émet un événement vers le webhook configuré. Retourne True si livré (2xx/3xx)."""
    url = settings.WEBHOOK_URL
    if not url:
        return False

    body = json.dumps(
        {"event": event, "source": "argus",
         "timestamp": datetime.now(timezone.utc).isoformat(), "data": data},
        ensure_ascii=False, default=str,
    ).encode("utf-8")

    headers = {"Content-Type": "application/json", "X-Argus-Event": event}
    if settings.WEBHOOK_SECRET:
        sig = hmac.new(settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        headers["X-Argus-Signature"] = "sha256=" + sig

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(url, content=body, headers=headers)
            ok = r.status_code < 400
            if not ok:
                logger.warning("Webhook '%s' → HTTP %s", event, r.status_code)
            return ok
    except Exception as e:
        logger.warning("Webhook '%s' échoué : %s", event, e)
        return False
