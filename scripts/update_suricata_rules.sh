#!/bin/bash
# ============================================================
# Mise à jour automatique des règles Suricata
# Via suricata-update (ET Open, Emerging Threats)
# ============================================================

set -euo pipefail

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [+] $*"; }
err() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [X] $*" >&2; }

log "Démarrage mise à jour règles Suricata..."

# Mettre à jour les règles via le conteneur Docker
if docker ps --format '{{.Names}}' | grep -q "suricata"; then
    docker exec suricata suricata-update --no-reload
    docker exec suricata suricata-update update-sources
    docker exec suricata suricata -T -c /etc/suricata/suricata.yaml -v

    # Recharger Suricata avec les nouvelles règles
    docker kill --signal=USR2 suricata 2>/dev/null && \
        log "Suricata rechargé avec les nouvelles règles" || \
        err "Erreur rechargement Suricata"
else
    # Mise à jour locale (si Suricata non containerisé)
    if command -v suricata-update &>/dev/null; then
        suricata-update
        suricatasc -c reload-rules /var/run/suricata/suricata-command.socket 2>/dev/null && \
            log "Règles rechargées via socket" || \
            log "Reload via socket échoué — redémarrage manuel requis"
    else
        err "suricata-update introuvable"
        exit 1
    fi
fi

log "Mise à jour terminée"
