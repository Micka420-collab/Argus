#!/usr/bin/env bash
# ============================================================
#  Argus — Sauvegarde des données
#  Sauvegarde les volumes Docker (OpenSearch, Wazuh, Redis, clés PQC…),
#  le fichier .env et les certificats TLS dans backups/argus-<horodatage>/.
#  Usage : ./backup.sh [dossier_destination]
# ============================================================
set -euo pipefail
C_RESET="\033[0m"; C_B="\033[1m"; C_BLUE="\033[38;5;75m"; C_GREEN="\033[38;5;78m"; C_YEL="\033[38;5;221m"; C_RED="\033[38;5;203m"
info(){ printf "${C_BLUE}▸${C_RESET} %s\n" "$*"; }
ok(){ printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
warn(){ printf "${C_YEL}!${C_RESET} %s\n" "$*"; }
die(){ printf "${C_RED}✗ %s${C_RESET}\n" "$*" >&2; exit 1; }
ASSUME_YES="${ARGUS_YES:-0}"
ask_yn(){ local a="${2:-n}"; if [ "$ASSUME_YES" = "1" ] || [ ! -e /dev/tty ]; then case "$a" in [Yy]*) return 0;; *) return 1;; esac; fi
  printf "${C_B}%s (y/n)${C_RESET} [%s] " "$1" "$a" > /dev/tty; read -r r < /dev/tty || true; case "${r:-$a}" in [Yy]*) return 0;; *) return 1;; esac; }

[ -f docker-compose.yml ] || die "Lancez ce script depuis le dossier Argus."
command -v docker >/dev/null 2>&1 || die "Docker introuvable."
if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"; elif command -v docker-compose >/dev/null 2>&1; then COMPOSE="docker-compose"; else COMPOSE=""; fi

# Volumes porteurs de données (suffixes ; le préfixe = nom de projet Compose)
SUFFIXES="opensearch_data wazuh_etc wazuh_data wazuh_queue redis_data pqc_keys suricata_rules"

STAMP="$(date +%Y%m%d-%H%M%S)"
BASE="${1:-backups}"
DEST="$BASE/argus-$STAMP"
mkdir -p "$DEST"
DEST_ABS="$(cd "$DEST" && pwd)"

# Arrêt recommandé pour une sauvegarde cohérente (OpenSearch surtout)
STOPPED=0
if [ -n "$COMPOSE" ] && ask_yn "Arrêter la stack pendant la sauvegarde (recommandé, cohérence des données) ?" "y"; then
  info "Arrêt temporaire de la stack…"; $COMPOSE stop >/dev/null 2>&1 || true; STOPPED=1
fi

info "Sauvegarde des volumes…"
COUNT=0
for v in $(docker volume ls -q); do
  for s in $SUFFIXES; do
    case "$v" in
      *_"$s"|"$s")
        info "  • $v"
        docker run --rm -v "$v":/v:ro -v "$DEST_ABS":/out alpine:3.20 \
          sh -c "tar czf /out/$s.tgz -C /v . 2>/dev/null" || warn "    échec pour $v"
        echo "$s.tgz <= $v" >> "$DEST/manifest.txt"
        COUNT=$((COUNT+1))
        ;;
    esac
  done
done

# .env + certificats (hors volumes)
[ -f .env ] && cp .env "$DEST/env.backup" && info "  • .env"
if [ -d nginx/certs ]; then cp -r nginx/certs "$DEST/certs" && info "  • nginx/certs"; fi

{ echo "argus_backup=$STAMP"; echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "volumes=$COUNT"; } >> "$DEST/manifest.txt"

# Redémarrage si on avait arrêté
if [ "$STOPPED" = "1" ] && [ -n "$COMPOSE" ]; then
  info "Redémarrage de la stack…"; $COMPOSE start >/dev/null 2>&1 || $COMPOSE up -d >/dev/null 2>&1 || true
fi

ok "Sauvegarde terminée : $DEST  ($COUNT volume(s))"
echo "  Restaurer avec : ./restore.sh \"$DEST\""
warn "Ce dossier contient des SECRETS (.env, clés, certificats) — stockez-le de façon sécurisée."
