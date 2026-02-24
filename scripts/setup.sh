#!/bin/bash
# ============================================================
# SOC Platform — Script d'installation
# Cible : Ubuntu 22.04 LTS sur Proxmox
#
# Usage :
#   chmod +x setup.sh
#   sudo ./setup.sh
#
# Ce script :
#   1. Installe Docker + Docker Compose
#   2. Configure le système (sysctl, ulimits, firewall)
#   3. Clone la plateforme SOC
#   4. Lance la stack
# ============================================================

set -euo pipefail
IFS=$'\n\t'

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[X]${NC} $*" >&2; }
info() { echo -e "${BLUE}[i]${NC} $*"; }

# ----------------------------------------------------------
# Vérifications préalables
# ----------------------------------------------------------
check_root() {
    if [[ $EUID -ne 0 ]]; then
        err "Ce script doit être exécuté en root (sudo ./setup.sh)"
        exit 1
    fi
}

check_os() {
    if [[ ! -f /etc/lsb-release ]]; then
        warn "OS non détecté comme Ubuntu — vérifier la compatibilité"
    else
        . /etc/lsb-release
        log "OS: $DISTRIB_DESCRIPTION"
        if [[ "$DISTRIB_RELEASE" != "22.04" ]]; then
            warn "Ubuntu 22.04 recommandé, version détectée: $DISTRIB_RELEASE"
        fi
    fi
}

check_resources() {
    local ram_gb cpu_count disk_gb

    ram_gb=$(free -g | awk '/^Mem:/{print $2}')
    cpu_count=$(nproc)
    disk_gb=$(df -BG / | awk 'NR==2{gsub("G",""); print $4}')

    info "RAM disponible  : ${ram_gb}GB (minimum recommandé: 8GB)"
    info "CPU cores       : $cpu_count"
    info "Espace disque   : ${disk_gb}GB libres (minimum recommandé: 50GB)"

    if [[ $ram_gb -lt 4 ]]; then
        err "RAM insuffisante: ${ram_gb}GB disponibles, 8GB requis"
        exit 1
    fi
    if [[ $disk_gb -lt 20 ]]; then
        err "Espace disque insuffisant: ${disk_gb}GB libres, 50GB requis"
        exit 1
    fi
}

# ----------------------------------------------------------
# Installation Docker
# ----------------------------------------------------------
install_docker() {
    log "Installation de Docker..."

    # Supprimer les anciennes versions
    apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

    # Dépendances
    apt-get update -qq
    apt-get install -y -qq \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        apt-transport-https

    # Clé GPG Docker officielle
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Dépôt Docker
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

    # Activer et démarrer Docker
    systemctl enable docker
    systemctl start docker

    log "Docker installé: $(docker --version)"
    log "Docker Compose: $(docker compose version)"
}

# ----------------------------------------------------------
# Configuration système
# ----------------------------------------------------------
configure_system() {
    log "Configuration système..."

    # Sysctl pour OpenSearch (vm.max_map_count)
    cat >> /etc/sysctl.conf << 'EOF'

# SOC Platform — OpenSearch
vm.max_map_count=262144
# Performance réseau
net.core.somaxconn=65535
net.ipv4.tcp_max_syn_backlog=65535
EOF

    sysctl -p > /dev/null

    # Ulimits pour Wazuh/OpenSearch
    cat >> /etc/security/limits.conf << 'EOF'

# SOC Platform
* soft nofile 65536
* hard nofile 65536
* soft memlock unlimited
* hard memlock unlimited
EOF

    log "Sysctl et ulimits configurés"

    # Désactiver swap (requis par OpenSearch)
    swapoff -a
    sed -i '/swap/d' /etc/fstab
    warn "Swap désactivé (requis par OpenSearch)"
}

# ----------------------------------------------------------
# Configuration firewall (UFW)
# ----------------------------------------------------------
configure_firewall() {
    log "Configuration firewall (UFW)..."

    # Installer UFW si absent
    apt-get install -y -qq ufw

    ufw --force reset

    # Politique par défaut : tout bloquer en entrée
    ufw default deny incoming
    ufw default allow outgoing

    # SSH (adapter le port si nécessaire)
    ufw allow 22/tcp comment "SSH"

    # Wazuh Dashboard (HTTPS)
    ufw allow 5601/tcp comment "Wazuh Dashboard"

    # SOC Frontend
    ufw allow 3000/tcp comment "SOC Frontend"

    # SOC API (accès interne uniquement en prod)
    # ufw allow from 10.0.0.0/8 to any port 8000 comment "SOC API (interne)"

    # Wazuh Agents
    ufw allow 1514/udp comment "Wazuh agents syslog"
    ufw allow 1515/tcp comment "Wazuh enrollment"

    ufw --force enable
    log "Firewall configuré:"
    ufw status numbered
}

# ----------------------------------------------------------
# Initialisation du projet
# ----------------------------------------------------------
setup_project() {
    local project_dir="/opt/soc-platform"
    log "Configuration du projet dans $project_dir..."

    mkdir -p "$project_dir"

    # Créer les fichiers vides requis
    touch "$project_dir/wazuh/lists/threat-intel-ips"
    touch "$project_dir/wazuh/lists/threat-intel-domains"
    touch "$project_dir/wazuh/lists/blocked-ips"

    # Copier les fichiers depuis le répertoire courant si applicable
    if [[ -f "docker-compose.yml" ]]; then
        log "Copie des fichiers du projet..."
        cp -r . "$project_dir/"
    fi

    # Créer le .env depuis l'exemple
    if [[ ! -f "$project_dir/.env" ]]; then
        if [[ -f "$project_dir/.env.example" ]]; then
            cp "$project_dir/.env.example" "$project_dir/.env"
            warn "Fichier .env créé depuis .env.example"
            warn "→ MODIFIER LE .env AVANT DE CONTINUER !"
            warn "   nano $project_dir/.env"
        fi
    fi

    # Permissions
    chown -R 1000:1000 "$project_dir" 2>/dev/null || true
    chmod 600 "$project_dir/.env" 2>/dev/null || true
}

# ----------------------------------------------------------
# Démarrage de la stack
# ----------------------------------------------------------
start_stack() {
    local project_dir="/opt/soc-platform"

    if [[ ! -f "$project_dir/.env" ]]; then
        err "Fichier .env manquant — configurer avant de démarrer"
        return 1
    fi

    # Vérifier que les mots de passe ont été changés
    if grep -q "ChangeMe" "$project_dir/.env"; then
        err "Le .env contient encore des valeurs 'ChangeMe' !"
        err "Modifier $project_dir/.env puis relancer: docker compose up -d"
        return 1
    fi

    log "Démarrage de la stack SOC..."
    cd "$project_dir"

    # Pull des images
    docker compose pull

    # Démarrage
    docker compose up -d

    log "Stack démarrée!"
    info ""
    info "Accès :"
    info "  Dashboard Wazuh  : https://$(hostname -I | awk '{print $1}'):5601"
    info "  SOC Frontend     : http://$(hostname -I | awk '{print $1}'):3000"
    info "  SOC API docs     : http://$(hostname -I | awk '{print $1}'):8000/docs"
    info ""
    info "Statut: docker compose ps"
    info "Logs:   docker compose logs -f [service]"
}

# ----------------------------------------------------------
# Post-installation
# ----------------------------------------------------------
post_install() {
    log "Configuration post-installation..."

    # Script de sync MISP en cron (désactivé par défaut)
    local cron_file="/etc/cron.d/soc-platform"
    cat > "$cron_file" << 'EOF'
# SOC Platform — Tâches planifiées
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Sync MISP → Wazuh (toutes les 30 minutes)
# */30 * * * * root python3 /opt/soc-platform/scripts/sync_misp.py >> /var/log/soc/sync_misp.log 2>&1

# Mise à jour règles Suricata (quotidien à 3h du matin)
# 0 3 * * * root /opt/soc-platform/scripts/update_suricata_rules.sh >> /var/log/soc/suricata_update.log 2>&1
EOF

    mkdir -p /var/log/soc
    log "Cron configuré (désactivé par défaut): $cron_file"
}

# ----------------------------------------------------------
# Programme principal
# ----------------------------------------------------------
main() {
    echo ""
    echo "╔════════════════════════════════════════╗"
    echo "║     SOC Platform — Installation        ║"
    echo "║     Cible: Ubuntu 22.04 / Proxmox      ║"
    echo "╚════════════════════════════════════════╝"
    echo ""

    check_root
    check_os
    check_resources

    echo ""
    warn "Ce script va installer Docker et configurer le système."
    read -rp "Continuer? [y/N] " confirm
    if [[ "${confirm,,}" != "y" ]]; then
        info "Installation annulée."
        exit 0
    fi

    # Mise à jour du système
    log "Mise à jour des paquets..."
    apt-get update -qq && apt-get upgrade -y -qq

    install_docker
    configure_system
    configure_firewall
    setup_project
    post_install

    echo ""
    log "Installation terminée!"
    echo ""
    warn "ÉTAPES SUIVANTES:"
    warn "1. Modifier /opt/soc-platform/.env avec tes vrais mots de passe"
    warn "2. Configurer l'interface réseau dans .env (NETWORK_INTERFACE)"
    warn "3. Lancer: cd /opt/soc-platform && docker compose up -d"
    warn "4. Attendre 2-3 minutes que tous les services démarrent"
    warn "5. Accéder au dashboard: https://$(hostname -I | awk '{print $1}'):5601"
    echo ""
}

main "$@"
