"""
Service de notifications multi-canal
Pushover · Telegram · Discord
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

import httpx

from api.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    """Envoie des alertes sur tous les canaux configurés en parallèle."""

    async def send_all(self, message: str, priority: str = "normal"):
        """Lance tous les canaux configurés en parallèle."""
        tasks = []

        if settings.PUSHOVER_TOKEN and settings.PUSHOVER_USER:
            tasks.append(self._pushover(message, priority))

        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
            tasks.append(self._telegram(message, priority))

        if settings.DISCORD_WEBHOOK:
            tasks.append(self._discord(message, priority))

        if not tasks:
            logger.warning("Aucun canal de notification configuré")
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error("Erreur canal de notification #%d: %s", i, r)

    # ----------------------------------------------------------
    # Pushover — Fiable, priorité emergency avec retry automatique
    # https://pushover.net/api
    # ----------------------------------------------------------
    async def _pushover(self, message: str, priority: str = "normal"):
        priority_map = {
            "critical": 2,  # Emergency — répète jusqu'à ACK
            "high":     1,  # High priority — bypass DND
            "normal":   0,  # Normal
            "low":     -1,  # Low priority
        }
        prio = priority_map.get(priority, 0)

        payload = {
            "token":   settings.PUSHOVER_TOKEN,
            "user":    settings.PUSHOVER_USER,
            "message": message,
            "priority": prio,
            "title":   "SOC Alert",
            "sound":   "siren" if priority == "critical" else "pushover",
        }

        # Priority 2 = répète jusqu'à ACK
        if priority == "critical":
            payload.update({
                "priority": 2,
                "retry":  60,     # Répète toutes les 60s
                "expire": 3600,   # Expire après 1h
                "html":   1,
            })

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://api.pushover.net/1/messages.json",
                data=payload,
            )
            r.raise_for_status()
            logger.debug("Pushover envoyé (priority=%s)", priority)

    # ----------------------------------------------------------
    # Telegram
    # https://core.telegram.org/bots/api
    # ----------------------------------------------------------
    async def _telegram(self, message: str, priority: str = "normal"):
        # Emoji selon priorité
        emoji_map = {"critical": "🔴", "high": "🟠", "normal": "🟡", "low": "🟢"}
        formatted = f"{emoji_map.get(priority, '🔵')} <b>SOC Alert</b>\n\n{message}"

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id":    settings.TELEGRAM_CHAT_ID,
            "text":       formatted,
            "parse_mode": "HTML",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            logger.debug("Telegram envoyé")

    # ----------------------------------------------------------
    # Discord Webhook
    # https://discord.com/developers/docs/resources/webhook
    # ----------------------------------------------------------
    async def _discord(self, message: str, priority: str = "normal"):
        color_map = {
            "critical": 0xFF0000,  # Rouge
            "high":     0xFF8C00,  # Orange
            "normal":   0x3498DB,  # Bleu
            "low":      0x2ECC71,  # Vert
        }
        payload = {
            "username": "SOC Bot",
            "embeds": [
                {
                    "title":       "⚠️ SOC Alert",
                    "description": message,
                    "color":       color_map.get(priority, 0x3498DB),
                    "timestamp":   datetime.utcnow().isoformat(),
                    "footer":      {"text": "SOC Platform v2.0"},
                }
            ],
        }

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(settings.DISCORD_WEBHOOK, json=payload)
            r.raise_for_status()
            logger.debug("Discord envoyé")
