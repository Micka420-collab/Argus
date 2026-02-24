"""
Playbooks automatiques — Réponse aux incidents
Déclenché selon le MITRE ATT&CK ID de l'alerte.
Les actions irréversibles (isolation réseau) demandent confirmation humaine.
"""
import asyncio
import logging
import subprocess
from enum import Enum
from typing import Callable, Dict, List

import httpx

from api.core.config import settings

logger = logging.getLogger(__name__)


class PlaybookTrigger(str, Enum):
    LSASS_DUMP      = "T1003.001"
    RANSOMWARE      = "T1486"
    BRUTE_FORCE     = "T1110"
    BRUTE_FORCE_RDP = "T1110.001"
    LATERAL_MOVE    = "T1021"
    PROCESS_INJECT  = "T1055"
    POWERSHELL      = "T1059.001"
    PERSISTENCE_RUN = "T1547.001"
    SHADOW_COPY_DEL = "T1490"
    DNS_C2          = "T1071.004"


class PlaybookEngine:
    """
    Moteur de playbooks.
    Chaque MITRE ID mappe vers une liste d'actions à exécuter dans l'ordre.
    """

    def __init__(self):
        self._registry: Dict[str, List[Callable]] = {
            PlaybookTrigger.LSASS_DUMP: [
                self.action_notify_analyst,
                self.action_request_isolation,    # Demande confirmation humaine
                self.action_snapshot_memory,
            ],
            PlaybookTrigger.RANSOMWARE: [
                self.action_isolate_network,       # Automatique (critique)
                self.action_snapshot_disk,
                self.action_notify_analyst,
            ],
            PlaybookTrigger.SHADOW_COPY_DEL: [
                self.action_isolate_network,
                self.action_notify_analyst,
            ],
            PlaybookTrigger.BRUTE_FORCE: [
                self.action_block_ip_firewall,
                self.action_notify_analyst,
            ],
            PlaybookTrigger.BRUTE_FORCE_RDP: [
                self.action_block_ip_firewall,
                self.action_notify_analyst,
            ],
            PlaybookTrigger.PROCESS_INJECT: [
                self.action_notify_analyst,
                self.action_request_isolation,
            ],
            PlaybookTrigger.POWERSHELL: [
                self.action_notify_analyst,
            ],
            PlaybookTrigger.DNS_C2: [
                self.action_block_ip_firewall,
                self.action_notify_analyst,
            ],
        }

    async def run(self, mitre_id: str, context: dict):
        """
        Exécute le playbook associé au MITRE ID.
        Toujours notifier l'analyste si aucun playbook spécifique.
        """
        actions = self._registry.get(mitre_id, [self.action_notify_analyst])

        logger.info(
            "Playbook déclenché: MITRE=%s agent=%s (%d actions)",
            mitre_id,
            context.get("agent_name", "?"),
            len(actions),
        )

        for action in actions:
            try:
                await action(context)
                logger.debug("Action %s OK", action.__name__)
            except Exception as e:
                logger.error("Action %s échouée: %s", action.__name__, e)
                # On continue même si une action échoue

    # ----------------------------------------------------------
    # Actions disponibles
    # ----------------------------------------------------------

    async def action_notify_analyst(self, ctx: dict):
        """Notification analyste avec contexte complet."""
        from api.services.notifications import NotificationService
        notif = NotificationService()
        mitre = ctx.get("mitre_id", "N/A")
        await notif.send_all(
            f"📋 Playbook déclenché\n"
            f"Machine: {ctx.get('agent_name', '?')} ({ctx.get('agent_ip', '?')})\n"
            f"MITRE: {mitre}\n"
            f"Alerte: {ctx.get('rule_desc', 'N/A')}\n"
            f"Niveau: {ctx.get('rule_level', '?')}/15\n"
            f"→ Analyse requise",
            priority="high",
        )

    async def action_request_isolation(self, ctx: dict):
        """
        Demande de confirmation d'isolation réseau via Pushover.
        L'analyste doit confirmer avant isolement.
        Pushover supporte des callbacks vers l'API SOC.
        """
        from api.services.notifications import NotificationService
        notif = NotificationService()
        agent = ctx.get("agent_name", "?")
        alert_id = ctx.get("alert_id", "")

        # URL de callback pour confirmation (endpoint REST)
        callback_url = f"http://soc-api:8000/api/v1/playbooks/confirm-isolation/{alert_id}"

        await notif.send_all(
            f"⚠️ ISOLATION REQUISE — Confirmation nécessaire\n"
            f"Machine: {agent}\n"
            f"Cause: {ctx.get('rule_desc', 'N/A')}\n"
            f"Confirmer via: {callback_url}\n"
            f"Ou répondre OUI à ce message (si Pushover configuré)",
            priority="critical",
        )

    async def action_isolate_network(self, ctx: dict):
        """
        Isolation réseau via Wazuh Active Response.
        Action AUTOMATIQUE (uniquement pour ransomware/critique).
        Bloque tout le trafic entrant/sortant sauf Wazuh.
        """
        agent_id = ctx.get("agent_id")
        if not agent_id:
            logger.error("Impossible d'isoler: agent_id manquant")
            return

        try:
            # Obtenir un token Wazuh
            token = await self._get_wazuh_token()

            async with httpx.AsyncClient(verify=False, timeout=15) as client:
                # Windows — bloquer via netsh advfirewall
                r = await client.put(
                    f"{settings.WAZUH_API_URL}/active-response/{agent_id}",
                    json={
                        "command": "firewall-drop",
                        "arguments": ["all"],
                        "alert": {"data": {"srcip": "all"}},
                    },
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                )
                r.raise_for_status()
                logger.warning(
                    "ISOLATION RÉSEAU — Agent %s isolé (alerte: %s)",
                    agent_id, ctx.get("alert_id"),
                )

            # Notifier confirmation d'isolation
            from api.services.notifications import NotificationService
            await NotificationService().send_all(
                f"🔒 MACHINE ISOLÉE\n"
                f"Agent: {ctx.get('agent_name')} (ID: {agent_id})\n"
                f"Cause: Ransomware / activité critique détectée\n"
                f"Action: Trafic réseau bloqué via Wazuh AR",
                priority="critical",
            )

        except Exception as e:
            logger.error("Erreur isolation réseau agent %s: %s", agent_id, e)

    async def action_block_ip_firewall(self, ctx: dict):
        """
        Bloque une IP dans la CDB list Wazuh.
        Déclenche le rechargement des règles.
        """
        ip = ctx.get("src_ip")
        if not ip:
            logger.warning("action_block_ip_firewall: src_ip manquant dans le contexte")
            return

        try:
            blocked_ips_file = "/var/ossec/etc/lists/blocked-ips"
            with open(blocked_ips_file, "a") as f:
                f.write(f"{ip}:blocked\n")

            # Rechargement des règles Wazuh
            result = subprocess.run(
                ["/var/ossec/bin/ossec-control", "reload"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("IP %s bloquée via Wazuh CDB list", ip)
            else:
                logger.error("Erreur reload Wazuh: %s", result.stderr)

        except PermissionError:
            logger.error("Pas les droits pour écrire dans %s", blocked_ips_file)
        except Exception as e:
            logger.error("Erreur block_ip_firewall pour %s: %s", ip, e)

    async def action_snapshot_memory(self, ctx: dict):
        """
        Déclenche un dump mémoire via WinPmem (Windows) ou LiME (Linux).
        Commande via Wazuh wodle command.
        À configurer selon l'environnement.
        """
        logger.info(
            "Snapshot mémoire demandé pour %s — implémenter via Wazuh wodle",
            ctx.get("agent_name"),
        )
        # TODO: Implémenter via Wazuh Active Response ou outil forensic dédié
        # Exemple: winpmem.exe --output c:\forensics\memory.dmp

    async def action_snapshot_disk(self, ctx: dict):
        """
        Snapshot disque pour préservation de preuves.
        À implémenter via Proxmox API ou outil forensic.
        """
        logger.info(
            "Snapshot disque demandé pour %s — implémenter via Proxmox API",
            ctx.get("agent_name"),
        )
        # TODO: Via Proxmox API: POST /nodes/{node}/qemu/{vmid}/snapshot

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    async def _get_wazuh_token(self) -> str:
        """Obtient un token JWT Wazuh pour l'API."""
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            r = await client.post(
                f"{settings.WAZUH_API_URL}/security/user/authenticate",
                auth=(settings.WAZUH_API_USER, settings.WAZUH_API_PASSWORD),
            )
            r.raise_for_status()
            return r.json()["data"]["token"]
