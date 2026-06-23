#!/usr/bin/env bash
# ============================================================
#  Argus — Désinstallation
#  Arrête la stack. Optionnel : supprimer les données (volumes)
#  et/ou les images Docker. Le dossier (.env, certs) reste à supprimer
#  manuellement si souhaité.
#  Usage : ./uninstall.sh
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

[ -f docker-compose.yml ] || die "Lancez ce script depuis le dossier Argus (docker-compose.yml introuvable)."
if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE="docker-compose"
else die "Docker Compose introuvable."; fi

warn "Cette opération va ARRÊTER Argus et supprimer ses conteneurs."
ask_yn "Continuer ?" "n" || { info "Annulé."; exit 0; }

DOWN="down --remove-orphans"
if ask_yn "Supprimer aussi les DONNÉES (volumes : alertes, investigations… IRRÉVERSIBLE) ?" "n"; then
  DOWN="$DOWN -v"; warn "Les volumes de données seront supprimés."
fi
if ask_yn "Supprimer les images Docker construites par Argus ?" "n"; then
  DOWN="$DOWN --rmi local"
fi

info "Arrêt de la stack…"
# --profile ai/anon pour inclure les services optionnels éventuels
# shellcheck disable=SC2086
$COMPOSE --profile ai --profile anon $DOWN

ok "Argus a été arrêté et désinstallé."
case "$DOWN" in *"-v"*) warn "Données supprimées (volumes effacés).";; esac
echo ""
info "Pour tout retirer définitivement, supprimez ce dossier :"
echo "    $(pwd)"
echo "  (il contient encore .env et nginx/certs — secrets et certificat)."
