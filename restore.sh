#!/usr/bin/env bash
# ============================================================
#  Argus — Restauration des données
#  Restaure une sauvegarde produite par backup.sh dans les volumes Docker
#  (+ .env et certificats). ÉCRASE les données actuelles.
#  Usage : ./restore.sh <dossier_de_sauvegarde>
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

SRC="${1:-}"
[ -n "$SRC" ] || die "Usage : ./restore.sh <dossier_de_sauvegarde>"
[ -d "$SRC" ] || die "Dossier introuvable : $SRC"
[ -f docker-compose.yml ] || die "Lancez ce script depuis le dossier Argus."
command -v docker >/dev/null 2>&1 || die "Docker introuvable."
if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"; elif command -v docker-compose >/dev/null 2>&1; then COMPOSE="docker-compose"; else COMPOSE=""; fi
SRC_ABS="$(cd "$SRC" && pwd)"

# Déterminer le préfixe de projet Compose :
#  1) depuis un volume existant *_opensearch_data ; 2) sinon depuis le nom du dossier
PROJECT=""
existing="$(docker volume ls -q | grep -E '_opensearch_data$' | head -1 || true)"
if [ -n "$existing" ]; then
  PROJECT="${existing%_opensearch_data}"
else
  PROJECT="${COMPOSE_PROJECT_NAME:-$(basename "$PWD" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9_-]//g')}"
fi
info "Projet Compose ciblé : $PROJECT"

warn "La restauration va ÉCRASER les données actuelles d'Argus."
ask_yn "Continuer ?" "n" || { info "Annulé."; exit 0; }

if [ -n "$COMPOSE" ]; then info "Arrêt de la stack…"; $COMPOSE stop >/dev/null 2>&1 || true; fi

info "Restauration des volumes…"
for tgz in "$SRC_ABS"/*.tgz; do
  [ -e "$tgz" ] || continue
  s="$(basename "$tgz" .tgz)"
  vol="${PROJECT}_${s}"
  docker volume create "$vol" >/dev/null
  info "  • $s.tgz → $vol"
  docker run --rm -v "$vol":/v -v "$SRC_ABS":/in:ro alpine:3.20 \
    sh -c "rm -rf /v/* /v/..?* 2>/dev/null; tar xzf /in/$s.tgz -C /v" || warn "    échec pour $vol"
done

# .env
if [ -f "$SRC_ABS/env.backup" ] && ask_yn "Restaurer aussi le fichier .env (secrets) ?" "y"; then
  cp "$SRC_ABS/env.backup" .env && chmod 600 .env && ok "  .env restauré"
fi
# Certificats
if [ -d "$SRC_ABS/certs" ] && ask_yn "Restaurer les certificats TLS ?" "y"; then
  mkdir -p nginx/certs && cp -r "$SRC_ABS/certs/." nginx/certs/ && ok "  certificats restaurés"
fi

if [ -n "$COMPOSE" ] && ask_yn "Redémarrer Argus maintenant ?" "y"; then
  PROFILES=""
  grep -qE '^LLM_PROVIDER=ollama' .env 2>/dev/null && PROFILES="$PROFILES --profile ai"
  grep -qE '^OSINT_ANON=true'     .env 2>/dev/null && PROFILES="$PROFILES --profile anon"
  # shellcheck disable=SC2086
  $COMPOSE $PROFILES up -d
fi

ok "Restauration terminée."
