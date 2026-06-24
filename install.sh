#!/usr/bin/env bash
# ============================================================
#  Argus — Installeur guidé (SOC autonome & post-quantique)
#  Nécessite les droits root (Docker, sysctl) : le script S'AUTO-ÉLÈVE via sudo
#  (un mot de passe sudo pourra être demandé). Pas besoin de préfixer par sudo.
#  Usage :
#    ./install.sh                 (ou : sudo ./install.sh)
#  En une commande (clone + install) :
#    curl -fsSL https://raw.githubusercontent.com/Micka420-collab/Argus/main/install.sh | bash
#  Sans questions (valeurs par défaut sûres) :
#    ARGUS_YES=1 ./install.sh
# ============================================================
set -euo pipefail

REPO_URL="https://github.com/Micka420-collab/Argus.git"
RAW_URL="https://raw.githubusercontent.com/Micka420-collab/Argus/main/install.sh"
C_RESET="\033[0m"; C_B="\033[1m"; C_BLUE="\033[38;5;75m"; C_GREEN="\033[38;5;78m"
C_YEL="\033[38;5;221m"; C_RED="\033[38;5;203m"; C_DIM="\033[2m"

info() { printf "${C_BLUE}▸${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
warn() { printf "${C_YEL}!${C_RESET} %s\n" "$*"; }
err()  { printf "${C_RED}✗ %s${C_RESET}\n" "$*" >&2; }
die()  { err "$*"; exit 1; }

banner() {
  printf "${C_BLUE}${C_B}"
  cat <<'BANNER'
    _
   / \   _ __ __ _ _   _ ___   SOC autonome & post-quantique
  / _ \ | '__/ _` | | | / __|  « Le SOC qui s'investigue lui-même »
 / ___ \| | | (_| | |_| \__ \
/_/   \_\_|  \__, |\__,_|___/   Installeur guidé
             |___/
BANNER
  printf "${C_RESET}\n"
}

# ---- Lecture interactive robuste (fonctionne même via `curl | bash`) -------
ASSUME_YES="${ARGUS_YES:-0}"
ask() { # ask "Question" "défaut" -> renvoie la réponse
  local q="$1" def="${2:-}" ans=""
  if [ "$ASSUME_YES" = "1" ] || [ ! -e /dev/tty ]; then echo "$def"; return; fi
  printf "${C_B}%s${C_RESET} ${C_DIM}[%s]${C_RESET} " "$q" "$def" > /dev/tty
  read -r ans < /dev/tty || true
  echo "${ans:-$def}"
}
ask_yn() { # ask_yn "Question" "y|n"
  local a; a="$(ask "$1 (y/n)" "$2")"
  case "$a" in [Yy]*) return 0;; *) return 1;; esac
}

# ---- Générateurs de secrets -----------------------------------------------
have() { command -v "$1" >/dev/null 2>&1; }
gen_hex()  { if have openssl; then openssl rand -hex 32; else head -c32 /dev/urandom | od -An -tx1 | tr -d ' \n'; fi; }
gen_pass() { # mot de passe fort (≥ classes requises par OpenSearch)
  local base
  if have openssl; then base="$(openssl rand -base64 24)"; else base="$(head -c24 /dev/urandom | base64)"; fi
  # Suffixe « Aa1! » garantit maj/min/chiffre/spécial ; « ! » est URL-safe
  # (contrairement à @ : / qui cassent REDIS_URL).
  echo "$(printf '%s' "$base" | tr -dc 'A-Za-z0-9' | head -c 24)Aa1!"
}

# ---- Droits administrateur requis (Docker, sysctl, installation) ----------
# S'auto-élève en root via sudo. Gère les deux cas : fichier (./install.sh) et
# pipe (curl … | bash, où $0 vaut « bash » → on re-télécharge sous sudo).
if [ "$(id -u)" -ne 0 ]; then
  if have sudo; then
    info "Argus nécessite les droits administrateur — élévation via sudo…"
    # -E est souvent refusé par sudoers ; on passe seulement ARGUS_YES explicitement.
    case "$0" in
      */install.sh|install.sh) exec sudo ARGUS_YES="$ASSUME_YES" bash "$0" "$@" ;;
      *)                       exec sudo ARGUS_YES="$ASSUME_YES" bash -c "$(curl -fsSL "$RAW_URL")" ;;
    esac
  else
    die "Droits root requis. Relancez en root (su -) puis 'bash install.sh', ou installez sudo."
  fi
fi

# ============================================================
banner

# ---- 1. Prérequis ----------------------------------------------------------
info "Vérification des prérequis… (exécution en root)"

if ! have docker; then
  warn "Docker n'est pas installé."
  if [ "$(uname -s)" = "Linux" ] && ask_yn "Installer Docker automatiquement (get.docker.com) ?" "y"; then
    curl -fsSL https://get.docker.com | sh || die "Échec de l'installation de Docker."
    usermod -aG docker "${SUDO_USER:-$USER}" 2>/dev/null || true
    ok "Docker installé. (Déconnexion/reconnexion conseillée pour les droits docker.)"
  else
    die "Docker requis. Voir https://docs.docker.com/get-docker/"
  fi
fi

if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"
elif have docker-compose;              then COMPOSE="docker-compose"
else die "Docker Compose v2 requis (plugin 'docker compose')."; fi
ok "Docker + Compose détectés."

# Garde-fou espace disque (images + build + éventuel modèle Ollama)
FREE_GB="$(df -PBG / 2>/dev/null | awk 'NR==2{gsub(/[A-Za-z]/,"",$4); print $4+0}')"
FREE_GB="${FREE_GB:-999}"
info "Espace disque libre : ${FREE_GB} Go"
if [ "$FREE_GB" -lt 15 ]; then
  warn "Disque faible (${FREE_GB} Go). Recommandé : >=15 Go sans IA, >=35 Go avec Ollama."
  ask_yn "Continuer quand même ?" "n" || die "Libère de l'espace (docker system prune -af) ou agrandis le disque, puis relance."
fi

# OpenSearch exige vm.max_map_count >= 262144 (Linux)
if [ "$(uname -s)" = "Linux" ]; then
  cur="$(cat /proc/sys/vm/max_map_count 2>/dev/null || echo 0)"
  if [ "$cur" -lt 262144 ]; then
    warn "vm.max_map_count=$cur (OpenSearch en exige 262144)."
    if ask_yn "Le corriger maintenant ?" "y"; then
      sysctl -w vm.max_map_count=262144 || warn "Échec sysctl — à régler manuellement."
      grep -q '^vm.max_map_count' /etc/sysctl.conf 2>/dev/null \
        || echo 'vm.max_map_count=262144' >> /etc/sysctl.conf 2>/dev/null || true
      ok "vm.max_map_count corrigé."
    fi
  fi
fi

# ---- 2. Récupérer le dépôt (idempotent) ------------------------------------
if [ -f docker-compose.yml ]; then
  : # déjà à la racine du dépôt
elif [ -d Argus ]; then
  info "Dépôt Argus déjà présent — réutilisation et mise à jour…"
  cd Argus
  git pull --ff-only 2>/dev/null || warn "git pull ignoré (modifs locales ?)."
else
  info "Clonage du dépôt Argus…"
  have git || die "git requis pour cloner le dépôt."
  git clone --depth 1 "$REPO_URL" Argus || die "Échec du clonage."
  cd Argus
fi
ok "Dépôt prêt : $(pwd)"

# ---- 3. Configuration (.env) ----------------------------------------------
if [ -f .env ]; then
  if ask_yn ".env existe déjà. Le RÉGÉNÉRER (écrase les secrets) ?" "n"; then rm -f .env; fi
fi

if [ ! -f .env ]; then
  info "Configuration de la plateforme…"
  DOMAIN="$(ask "Nom de domaine de la console"        "soc.lan")"
  ADMIN_USER="$(ask "Identifiant administrateur"       "admin")"

  LLM_PROVIDER="none"
  if ask_yn "Activer l'analyste IA local (Ollama) ? (~8 Go RAM + ~6 Go disque)" "n"; then
    if [ "${FREE_GB:-999}" -lt 30 ] && ! ask_yn "  Seulement ${FREE_GB:-?} Go libres — activer Ollama malgré le risque de disque plein ?" "n"; then
      warn "Ollama non activé (espace insuffisant) — IA en mode heuristique (fonctionne très bien)."
    else
      LLM_PROVIDER="ollama"
      echo "  Choix du modèle selon votre matériel :"
      echo "    qwen2.5:0.5b  → CPU lent / peu de RAM   (~15 s/analyse, qualité correcte)"
      echo "    qwen2.5:1.5b  → CPU standard (RECOMMANDÉ) (~30-90 s/analyse, bonne qualité)"
      echo "    qwen2.5:7b    → GPU conseillé             (lent en CPU pur : >2 min/analyse)"
      LLM_MODEL="$(ask "Modèle Ollama" "qwen2.5:1.5b")"
      # Garde-fou : éviter qu'un « y/o/oui » saisi par erreur devienne le modèle.
      case "$LLM_MODEL" in
        ""|y|Y|yes|Yes|YES|o|O|oui|Oui|n|N|no|No|non|Non) LLM_MODEL="qwen2.5:1.5b" ;;
      esac
      [ "${#LLM_MODEL}" -lt 3 ] && LLM_MODEL="qwen2.5:1.5b"
    fi
  fi
  PQC_JWT="false"; ask_yn "Activer les jetons post-quantiques (JWT Ed25519) ?" "n" && PQC_JWT="true"
  OSINT_ANON="false"; ENABLE_ANON="n"
  if ask_yn "Anonymiser l'OSINT via Tor (passerelle anon-gateway) ?" "n"; then OSINT_ANON="true"; ENABLE_ANON="y"; fi
  ABUSEIPDB_KEY="$(ask "Clé AbuseIPDB (optionnel, Entrée pour ignorer)" "")"
  VIRUSTOTAL_KEY="$(ask "Clé VirusTotal (optionnel, Entrée pour ignorer)" "")"

  # Interface réseau pour Suricata (Proxmox/Ubuntu = souvent ens18, pas eth0)
  IFACE="$(ip route show default 2>/dev/null | awk '{print $5; exit}')"
  IFACE="${IFACE:-eth0}"
  info "Interface réseau détectée : $IFACE"

  info "Génération des secrets…"
  SECRET_KEY="$(gen_hex)"
  ADMIN_PASSWORD="$(gen_pass)"
  OPENSEARCH_PASSWORD="$(gen_pass)"
  REDIS_PASSWORD="$(gen_pass)"
  WAZUH_API_PASSWORD="$(gen_pass)"
  DASHBOARD_PASSWORD="$(gen_pass)"

  cat > .env <<ENV
# Généré par install.sh le $(date -u +%Y-%m-%dT%H:%M:%SZ)
SECRET_KEY=${SECRET_KEY}
JWT_ALGORITHM=HS256
ENVIRONMENT=production
SOC_DOMAIN=${DOMAIN}
NETWORK_INTERFACE=${IFACE}
WAZUH_API_USER=wazuh-wui
DASHBOARD_USERNAME=kibanaserver

ADMIN_USERNAME=${ADMIN_USER}
ADMIN_PASSWORD=${ADMIN_PASSWORD}

OPENSEARCH_PASSWORD=${OPENSEARCH_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
WAZUH_API_PASSWORD=${WAZUH_API_PASSWORD}
DASHBOARD_PASSWORD=${DASHBOARD_PASSWORD}

LLM_PROVIDER=${LLM_PROVIDER}
LLM_MODEL=${LLM_MODEL:-}
AI_AUTO_INVESTIGATE=false

PQC_JWT=${PQC_JWT}
TLS_GROUPS=X25519MLKEM768:X25519:secp256r1

OSINT_ANON=${OSINT_ANON}
$( [ "$OSINT_ANON" = "true" ] && echo "OUTBOUND_PROXY=socks5://anon-gateway:9050" )
$( [ "$OSINT_ANON" = "true" ] && echo "TOR_CONTROL_URL=http://anon-gateway:9052/newnym" )

ABUSEIPDB_KEY=${ABUSEIPDB_KEY}
VIRUSTOTAL_KEY=${VIRUSTOTAL_KEY}
ENV
  chmod 600 .env
  ok "Fichier .env généré (permissions 600)."
else
  ok ".env conservé."
  ADMIN_USER="$(grep -E '^ADMIN_USERNAME=' .env | cut -d= -f2-)"; ADMIN_USER="${ADMIN_USER:-admin}"
  ADMIN_PASSWORD="$(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2-)"
  DOMAIN="$(grep -E '^SOC_DOMAIN=' .env | cut -d= -f2-)"; DOMAIN="${DOMAIN:-soc.lan}"
  LLM_PROVIDER="$(grep -E '^LLM_PROVIDER=' .env | cut -d= -f2- || echo none)"
  ENABLE_ANON="$(grep -qE '^OSINT_ANON=true' .env && echo y || echo n)"
fi

# ---- Identifiants : sauvegarde + affichage (avant le build, au cas où) ------
CREDS_FILE="$(pwd)/argus-credentials.txt"
{
  echo "Argus — identifiants de connexion"
  echo "Console      : https://${DOMAIN:-soc.lan}  (ou https://<IP-de-la-VM>)"
  echo "Identifiant  : ${ADMIN_USER:-admin}"
  echo "Mot de passe : ${ADMIN_PASSWORD:-voir .env}"
} > "$CREDS_FILE" 2>/dev/null || true
chmod 600 "$CREDS_FILE" 2>/dev/null || true
printf "\n${C_GREEN}${C_B}── Identifiants de connexion ──${C_RESET}\n"
printf "  Identifiant  : ${C_B}%s${C_RESET}\n"   "${ADMIN_USER:-admin}"
printf "  Mot de passe : ${C_B}%s${C_RESET}\n"   "${ADMIN_PASSWORD:-voir .env}"
printf "  ${C_DIM}Sauvegardés dans %s${C_RESET}\n\n" "$CREDS_FILE"

# ---- 4. Certificat TLS -----------------------------------------------------
mkdir -p nginx/certs
if [ ! -f nginx/certs/soc.crt ] || [ ! -f nginx/certs/soc.key ]; then
  info "Génération d'un certificat TLS auto-signé…"
  if have openssl; then
    openssl req -x509 -newkey rsa:4096 -nodes -days 825 \
      -keyout nginx/certs/soc.key -out nginx/certs/soc.crt \
      -subj "/C=FR/O=Argus/CN=${DOMAIN}" \
      -addext "subjectAltName=DNS:${DOMAIN},DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1 \
      && ok "Certificat généré (remplacer par un certificat valide en production)." \
      || warn "Échec OpenSSL — fournir manuellement nginx/certs/soc.{crt,key}."
  else
    warn "OpenSSL absent — fournir manuellement nginx/certs/soc.{crt,key}."
  fi
else
  ok "Certificat TLS déjà présent."
fi

# ---- 5. Construction & démarrage ------------------------------------------
PROFILES=""
[ "${LLM_PROVIDER:-none}" = "ollama" ] && PROFILES="$PROFILES --profile ai"
[ "${ENABLE_ANON:-n}" = "y" ]          && PROFILES="$PROFILES --profile anon"

info "Construction des images (peut prendre quelques minutes)…"
# shellcheck disable=SC2086
$COMPOSE $PROFILES build

info "Démarrage de la stack…"
# shellcheck disable=SC2086
$COMPOSE $PROFILES up -d

if [ "${LLM_PROVIDER:-none}" = "ollama" ]; then
  info "Téléchargement du modèle LLM (${LLM_MODEL:-qwen2.5:1.5b})…"
  $COMPOSE exec -T ollama ollama pull "${LLM_MODEL:-qwen2.5:1.5b}" || warn "À relancer : docker compose exec ollama ollama pull ${LLM_MODEL:-qwen2.5:1.5b}"
  # Pré-chargement en mémoire : la 1ʳᵉ investigation IA serait sinon très lente
  # (chargement à froid de plusieurs Go). On ignore les erreurs (non bloquant).
  info "Pré-chargement du modèle en mémoire…"
  $COMPOSE exec -T ollama ollama run "${LLM_MODEL:-qwen2.5:1.5b}" "ok" >/dev/null 2>&1 || true
fi

# ---- 6. Récapitulatif ------------------------------------------------------
printf "\n${C_GREEN}${C_B}========================================${C_RESET}\n"
ok "Argus est lancé !"
printf "\n"
printf "  ${C_B}Console${C_RESET}      : https://%s  (ou https://localhost)\n" "$DOMAIN"
printf "  ${C_B}Présentation${C_RESET} : https://localhost/welcome\n"
printf "  ${C_B}Identifiant${C_RESET}  : %s\n" "${ADMIN_USER:-admin}"
printf "  ${C_B}Mot de passe${C_RESET} : %s\n" "${ADMIN_PASSWORD:-voir .env}"
printf "  ${C_DIM}(aussi sauvegardés dans %s)${C_RESET}\n" "${CREDS_FILE:-argus-credentials.txt}"
printf "\n"
warn "Le certificat est auto-signé : votre navigateur affichera un avertissement (normal en local)."
printf "${C_DIM}  État des services : %s ps${C_RESET}\n" "$COMPOSE"
printf "${C_DIM}  Logs API          : %s logs -f soc-api${C_RESET}\n" "$COMPOSE"
printf "${C_DIM}  Arrêter           : %s down${C_RESET}\n" "$COMPOSE"
printf "${C_GREEN}${C_B}========================================${C_RESET}\n"
