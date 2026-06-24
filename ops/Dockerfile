# ============================================================
# argus-ops — agent d'exploitation privilégié
# ------------------------------------------------------------
# Consomme une file Redis et exécute git pull / docker compose.
# Isolé à ce seul rôle : c'est le SEUL conteneur avec accès au socket Docker,
# ce qui garde soc-api non privilégié.
# ============================================================
FROM docker:27-cli

# docker compose v2 (plugin), git (pull) et redis-cli (file de commandes)
RUN apk add --no-cache git redis docker-cli-compose bash

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
