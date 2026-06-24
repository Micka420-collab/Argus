#!/bin/sh
# ============================================================
# argus-ops — boucle d'exécution des commandes d'exploitation
# Écoute la file Redis "argus:ops:queue" et exécute update / restart.
# ============================================================
set -u

# Chemin hôte réel du dépôt (monté à l'identique). Voir docker-compose.yml.
REPO="${ARGUS_HOST_DIR:-/opt/argus}"
QUEUE="argus:ops:queue"
STATUS="argus:ops:status"
RHOST="${REDIS_HOST:-redis}"
RPORT="${REDIS_PORT:-6379}"
RPASS="${REDIS_PASSWORD:-}"
COMPOSE="docker compose -f ${REPO}/docker-compose.yml --profile ai"
APP_SERVICES="soc-api soc-frontend nginx"

rcli() {
  if [ -n "$RPASS" ]; then
    redis-cli -h "$RHOST" -p "$RPORT" -a "$RPASS" --no-auth-warning "$@"
  else
    redis-cli -h "$RHOST" -p "$RPORT" "$@"
  fi
}

set_status() { rcli SET "$STATUS" "$1" >/dev/null 2>&1; }

echo "[argus-ops] démarré — écoute de la file '$QUEUE' sur $RHOST:$RPORT"

# Attendre que Redis réponde
while ! rcli PING >/dev/null 2>&1; do
  echo "[argus-ops] attente de Redis…"; sleep 2
done
echo "[argus-ops] connecté à Redis. Prêt."

while true; do
  # BLPOP bloque jusqu'à 30 s puis reboucle (permet de rester réactif aux logs)
  CMD=$(rcli --no-auth-warning BLPOP "$QUEUE" 30 2>/dev/null | tail -n 1)
  [ -z "$CMD" ] && continue
  echo "[argus-ops] commande reçue : $CMD"

  case "$CMD" in
    update)
      set_status "running:update"
      echo "[argus-ops] git pull…"
      if git -C "$REPO" pull --ff-only; then
        echo "[argus-ops] reconstruction des images applicatives…"
        # IMPORTANT : ne JAMAIS recréer argus-ops ici (on se tuerait en plein
        # update). On reconstruit les images locales puis on recrée tous les
        # services SAUF argus-ops lui-même.
        TARGETS=$($COMPOSE config --services 2>/dev/null | grep -v '^argus-ops$' | tr '\n' ' ')
        [ -z "$TARGETS" ] && TARGETS="soc-api soc-frontend nginx"
        # shellcheck disable=SC2086
        if $COMPOSE build soc-api soc-frontend nginx && $COMPOSE up -d $TARGETS; then
          # Nginx doit re-résoudre les nouvelles IP des conteneurs recréés
          $COMPOSE restart nginx >/dev/null 2>&1 || true
          set_status "done:update"
          echo "[argus-ops] mise à jour terminée."
        else
          set_status "error:update (build)"
          echo "[argus-ops] échec build/up."
        fi
      else
        set_status "error:update (git pull)"
        echo "[argus-ops] échec git pull (modifs locales ?)."
      fi
      ;;
    restart)
      set_status "running:restart"
      echo "[argus-ops] redémarrage de : $APP_SERVICES"
      # shellcheck disable=SC2086
      if $COMPOSE restart $APP_SERVICES; then
        set_status "done:restart"
        echo "[argus-ops] redémarrage terminé."
      else
        set_status "error:restart"
        echo "[argus-ops] échec redémarrage."
      fi
      ;;
    *)
      echo "[argus-ops] commande inconnue : $CMD"
      set_status "error:unknown:$CMD"
      ;;
  esac
done
