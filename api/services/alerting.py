"""
Moteur d'alerting — Cœur du SOC
Polling OpenSearch → Déduplication → Enrichissement → Notification
"""
import asyncio
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional

from api.core.config import settings
from api.services.opensearch import OpenSearchClient
from api.services.notifications import NotificationService
from api.services.enrichment import EnrichmentService
from api.services.deduplication import is_duplicate

logger = logging.getLogger(__name__)


class AlertEngine:
    """
    Moteur d'alerting principal.
    Tourne en arrière-plan et traite les alertes Wazuh en continu.
    """

    def __init__(self):
        self.os_client = OpenSearchClient()
        self.notif = NotificationService()
        self.enrichment = EnrichmentService()

        # Groupement des alertes non-critiques
        self._group_buffer: Dict[str, List[dict]] = defaultdict(list)

        # Tâches asyncio
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self):
        """Démarre les workers en arrière-plan."""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._poll_loop(), name="poll_opensearch"),
            asyncio.create_task(self._flush_loop(), name="flush_groups"),
        ]
        logger.info("AlertEngine démarré")

    async def stop(self):
        """Arrête proprement les workers."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("AlertEngine arrêté")

    # ----------------------------------------------------------
    # Workers principaux
    # ----------------------------------------------------------

    async def _poll_loop(self):
        """Interroge OpenSearch toutes les N secondes."""
        logger.info(
            "Démarrage polling OpenSearch (intervalle: %ds, niveau min: %d)",
            settings.POLL_INTERVAL_SECONDS,
            settings.ALERT_MIN_LEVEL,
        )
        while self._running:
            try:
                alerts = await self.os_client.get_recent_alerts(
                    min_level=settings.ALERT_MIN_LEVEL,
                    since=datetime.utcnow() - timedelta(seconds=settings.POLL_INTERVAL_SECONDS + 5),
                )
                for alert in alerts:
                    await self._process_alert(alert)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Erreur polling: %s", e)

            await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)

    async def _flush_loop(self):
        """Envoie les alertes groupées périodiquement."""
        while self._running:
            try:
                await asyncio.sleep(settings.GROUP_FLUSH_SECONDS)
                await self._flush_all_groups()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Erreur flush groups: %s", e)

    # ----------------------------------------------------------
    # Pipeline de traitement
    # ----------------------------------------------------------

    async def _process_alert(self, alert: dict):
        """
        Pipeline complet de traitement d'une alerte :
        1. Maintenance check → 2. Déduplication → 3. Enrichissement
        4. Priorisation → 5. Notification / Groupement
        """
        alert_id = alert.get("id", "")
        rule = alert.get("rule", {})
        agent = alert.get("agent", {})
        level = rule.get("level", 0)

        # 1. Mode maintenance ?
        agent_ip = agent.get("ip")
        if agent_ip and await self._is_maintenance(agent_ip):
            logger.debug("Alerte ignorée — asset en maintenance: %s", agent_ip)
            return

        # 2. Déduplication
        if await is_duplicate(alert):
            logger.debug("Alerte dupliquée ignorée: rule=%s agent=%s", rule.get("id"), agent.get("name"))
            return

        # 3. Enrichissement IP (async, non bloquant)
        src_ip = alert.get("data", {}).get("srcip") or alert.get("src_ip")
        if src_ip:
            asyncio.create_task(
                self.enrichment.enrich_ip(src_ip, alert_id),
                name=f"enrich_{src_ip}",
            )

        # 3b. Investigation IA autonome sur alerte critique (pilier Qevlar)
        if settings.AI_AUTO_INVESTIGATE and level >= settings.ALERT_CRITICAL_LEVEL:
            asyncio.create_task(
                self._run_ai_investigation(alert),
                name=f"ai_investigate_{alert_id}",
            )

        # 4. Priorisation + playbooks
        mitre_ids = rule.get("mitre", {}).get("id", [])

        # Déclencher playbooks MITRE si applicable
        if mitre_ids:
            asyncio.create_task(
                self._trigger_playbooks(mitre_ids, alert),
                name=f"playbook_{alert_id}",
            )

        # 5. Notification selon niveau
        if level >= settings.ALERT_CRITICAL_LEVEL:
            await self._send_critical(alert)
            await self._broadcast(alert)
        elif level >= settings.ALERT_MIN_LEVEL:
            group_key = f"{rule.get('id')}_{agent.get('name', 'unknown')}"
            self._group_buffer[group_key].append(alert)

    async def _run_ai_investigation(self, alert: dict):
        """Lance l'agent d'investigation autonome (best-effort, non bloquant)."""
        try:
            from api.services.ai_investigation import AiInvestigationAgent
            report = await AiInvestigationAgent().run(alert, source="auto")
            logger.info(
                "Investigation IA autonome terminée: %s → %s",
                report.get("id"), report.get("decision"),
            )
        except Exception as e:
            logger.error("Investigation IA autonome échouée: %s", e)

    async def _trigger_playbooks(self, mitre_ids: List[str], alert: dict):
        """Déclenche les playbooks correspondant aux TTPs MITRE."""
        try:
            from api.services.playbooks import PlaybookEngine
            engine = PlaybookEngine()
            context = {
                "alert_id": alert.get("id"),
                "agent_id": alert.get("agent", {}).get("id"),
                "agent_name": alert.get("agent", {}).get("name"),
                "agent_ip": alert.get("agent", {}).get("ip"),
                "src_ip": alert.get("data", {}).get("srcip"),
                "rule_desc": alert.get("rule", {}).get("description"),
                "rule_level": alert.get("rule", {}).get("level"),
            }
            for mitre_id in mitre_ids:
                await engine.run(mitre_id, context)
        except Exception as e:
            logger.error("Erreur déclenchement playbooks: %s", e)

    # ----------------------------------------------------------
    # Envoi de notifications
    # ----------------------------------------------------------

    async def _send_critical(self, alert: dict):
        rule = alert.get("rule", {})
        agent = alert.get("agent", {})
        mitre_ids = rule.get("mitre", {}).get("id", [])

        message = (
            f"🔴 CRITIQUE — {rule.get('description', 'Alerte inconnue')}\n"
            f"Machine: {agent.get('name', 'Unknown')} ({agent.get('ip', '?')})\n"
            f"MITRE: {', '.join(mitre_ids) if mitre_ids else 'N/A'}\n"
            f"Niveau: {rule.get('level')}/15\n"
            f"ID Alerte: {alert.get('id', '?')}"
        )
        await self.notif.send_all(message, priority="critical")
        logger.warning("Alerte critique envoyée: %s", rule.get("description"))

    async def _send_grouped(self, group_key: str, events: List[dict]):
        if not events:
            return
        first = events[0]
        rule = first.get("rule", {})
        count = len(events)
        machines = list({e.get("agent", {}).get("name", "?") for e in events})
        machines_str = ", ".join(machines[:3])
        if len(machines) > 3:
            machines_str += f"... (+{len(machines) - 3})"

        message = (
            f"🟠 {count}x {rule.get('description', 'Alertes')}\n"
            f"Machines: {machines_str}\n"
            f"Niveau: {rule.get('level')}/15"
        )
        await self.notif.send_all(message, priority="high")

    async def _flush_all_groups(self):
        """Vide le buffer et envoie toutes les alertes groupées."""
        buffer_copy = dict(self._group_buffer)
        self._group_buffer.clear()
        for group_key, events in buffer_copy.items():
            if events:
                try:
                    await self._send_grouped(group_key, events)
                except Exception as e:
                    logger.error("Erreur envoi groupe %s: %s", group_key, e)

    async def _broadcast(self, alert: dict):
        """Broadcast WebSocket vers le frontend."""
        try:
            from api.routers.alerts import broadcast_alert
            await broadcast_alert(alert)
        except Exception as e:
            logger.debug("Erreur broadcast WS: %s", e)

    # ----------------------------------------------------------
    # Maintenance
    # ----------------------------------------------------------

    async def _is_maintenance(self, asset_ip: str) -> bool:
        """Vérifie si un asset est en mode maintenance (via Redis)."""
        try:
            from api.services.deduplication import get_redis
            r = await get_redis()
            return bool(await r.exists(f"maintenance:{asset_ip}"))
        except Exception:
            return False
