#!/usr/bin/env python3
"""
Synchronisation MISP → Wazuh CDB Lists
Télécharge les IoCs de MISP et les injecte dans les listes de blocage Wazuh.

Utilisation :
  python3 sync_misp.py
  python3 sync_misp.py --types ip-dst ip-src domain --limit 10000

Cron (toutes les 30 minutes) :
  */30 * * * * /usr/bin/python3 /opt/soc/scripts/sync_misp.py >> /var/log/soc/sync_misp.log 2>&1
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------
# Configuration (depuis variables d'environnement ou .env)
# ----------------------------------------------------------
MISP_URL        = os.getenv("MISP_URL", "https://misp.local")
MISP_KEY        = os.getenv("MISP_KEY", "")
OUTPUT_DIR      = Path(os.getenv("WAZUH_LISTS_DIR", "/var/ossec/etc/lists"))
WAZUH_CONTROL   = "/var/ossec/bin/ossec-control"

OUTPUT_FILES = {
    "ips":     OUTPUT_DIR / "threat-intel-ips",
    "domains": OUTPUT_DIR / "threat-intel-domains",
    "hashes":  OUTPUT_DIR / "threat-intel-hashes",
}

DEFAULT_TYPES = {
    "ips":     ["ip-dst", "ip-src"],
    "domains": ["domain", "hostname"],
    "hashes":  ["md5", "sha1", "sha256"],
}


def fetch_misp_attributes(
    attribute_types: List[str],
    limit: int = 5000,
    to_ids: bool = True,
) -> List[str]:
    """Récupère les attributs MISP du type spécifié."""
    if not MISP_KEY:
        logger.error("MISP_KEY non configurée — impossible de se connecter")
        sys.exit(1)

    headers = {
        "Authorization": MISP_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "returnFormat": "json",
        "type":         attribute_types,
        "to_ids":       to_ids,
        "limit":        limit,
        "enforceWarninglist": True,
    }

    try:
        r = requests.post(
            f"{MISP_URL}/attributes/restSearch",
            headers=headers,
            json=payload,
            verify=False,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        attributes = data.get("response", {}).get("Attribute", [])
        values = [attr["value"] for attr in attributes if attr.get("value")]
        logger.info("MISP: %d attributs récupérés pour types %s", len(values), attribute_types)
        return values
    except requests.exceptions.ConnectionError:
        logger.error("Impossible de se connecter à MISP: %s", MISP_URL)
        return []
    except requests.exceptions.HTTPError as e:
        logger.error("Erreur HTTP MISP: %s", e)
        return []


def write_cdb_list(filepath: Path, values: List[str], label: str = "malicious") -> int:
    """
    Écrit une CDB list Wazuh.
    Format: valeur:label
    """
    if not values:
        logger.warning("Aucune valeur à écrire dans %s", filepath)
        return 0

    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Backup de l'ancien fichier
    if filepath.exists():
        backup = filepath.with_suffix(".bak")
        filepath.rename(backup)

    written = 0
    with open(filepath, "w") as f:
        f.write(f"# SOC Platform — Threat Intel {label}\n")
        f.write(f"# Généré le {datetime.utcnow().isoformat()}Z\n")
        f.write(f"# Source: MISP ({MISP_URL})\n")
        f.write(f"# Total: {len(values)} IoCs\n\n")

        seen = set()
        for value in values:
            value = value.strip()
            if not value or value in seen:
                continue
            seen.add(value)
            f.write(f"{value}:{label}\n")
            written += 1

    logger.info("Fichier écrit: %s (%d IoCs uniques)", filepath, written)
    return written


def reload_wazuh():
    """Recharge les listes Wazuh pour appliquer les changements."""
    if not Path(WAZUH_CONTROL).exists():
        logger.warning("wazuh-control introuvable — reload manuel requis")
        return

    try:
        result = subprocess.run(
            [WAZUH_CONTROL, "reload"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("Wazuh rechargé avec succès")
        else:
            logger.error("Erreur reload Wazuh: %s", result.stderr)
    except subprocess.TimeoutExpired:
        logger.error("Timeout lors du reload Wazuh")
    except PermissionError:
        logger.error("Pas les droits pour exécuter wazuh-control")


def main():
    parser = argparse.ArgumentParser(description="Sync MISP → Wazuh CDB Lists")
    parser.add_argument("--types", nargs="*", choices=["ips", "domains", "hashes"],
                        default=["ips"], help="Types d'IoCs à synchroniser")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Nombre maximum d'IoCs par type (défaut: 5000)")
    parser.add_argument("--no-reload", action="store_true",
                        help="Ne pas recharger Wazuh après sync")
    args = parser.parse_args()

    start = datetime.utcnow()
    total_written = 0

    for ioc_type in args.types:
        logger.info("=== Synchronisation type: %s ===", ioc_type)
        attribute_types = DEFAULT_TYPES[ioc_type]
        values = fetch_misp_attributes(attribute_types, limit=args.limit)
        if values:
            written = write_cdb_list(OUTPUT_FILES[ioc_type], values, label=ioc_type.rstrip("s"))
            total_written += written

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info("Synchronisation terminée: %d IoCs écrits en %.1fs", total_written, elapsed)

    if total_written > 0 and not args.no_reload:
        reload_wazuh()


if __name__ == "__main__":
    main()
