#!/usr/bin/env bash
# ============================================================
#  Argus — Mise à jour
#  Récupère la dernière version, reconstruit et redémarre la stack.
#  Préserve .env, certificats et données (volumes).
#  Usage : ./update.sh        (ARGUS_YES=1 ./update.sh pour ne rien demander)
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

# Profils actifs (déduits du .env)
PROFILES=""
grep -qE '^LLM_PROVIDER=ollama' .env 2>/dev/null && PROFILES="$PROFILES --profile ai"
grep -qE '^OSINT_ANON=true'     .env 2>/dev/null && PROFILES="$PROFILES --profile anon"

info "Récupération de la dernière version (git pull)…"
if git rev-parse --git-dir >/dev/null 2>&1; then
  git pull --ff-only || warn "git pull impossible (modifs locales ?). Poursuite avec le code actuel."
else
  warn "Pas un dépôt git — étape git pull ignorée."
fi

info "Reconstruction des images…"
# shellcheck disable=SC2086
$COMPOSE $PROFILES build

info "Redémarrage de la stack…"
# shellcheck disable=SC2086
$COMPOSE $PROFILES up -d

if ask_yn "Nettoyer les anciennes images Docker inutilisées ?" "y"; then
  docker image prune -f >/dev/null 2>&1 || true
  ok "Images inutilisées nettoyées."
fi

ok "Mise à jour terminée."
# shellcheck disable=SC2086
$COMPOSE $PROFILES ps
