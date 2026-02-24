# 🛡️ Argus — SOC Platform

Plateforme de surveillance de sécurité réseau open-source, déployable sur Proxmox avec Docker.

## Stack technique

| Composant | Rôle |
|-----------|------|
| **Wazuh** | SIEM / EDR — collecte et corrélation d'alertes |
| **Suricata** | IDS/IPS — détection réseau temps réel |
| **OpenSearch** | Moteur de recherche et stockage des alertes |
| **FastAPI** | Backend REST + WebSocket |
| **React + Tailwind** | Dashboard glassmorphisme temps réel |
| **Redis** | Cache investigations OSINT + stats |
| **Nginx** | Reverse proxy TLS (seul port exposé : 443) |

## Fonctionnalités principales

- 📡 **Alertes temps réel** via WebSocket sécurisé (JWT)
- 🔍 **Investigation OSINT** : qui attaque ? (AbuseIPDB, VirusTotal, RDAP, ip-api)
- 🗺️ **Score de risque 0-100** avec actions recommandées automatiquement
- 🖥️ **Inventaire des assets** supervisés par Wazuh
- 📋 **Règles Wazuh** avec tags MITRE ATT&CK
- 📦 **Cache Redis** pour économiser les quotas API OSINT
- 🔐 **Auth JWT + RBAC** (admin / analyst / viewer)
- 🏠 **Freebox Free** : collecteur API officiel Freebox → Wazuh

## Démarrage rapide

```bash
git clone https://github.com/Micka420-collab/Argus.git
cd Argus
cp .env.example .env
# Éditer .env avec vos secrets
docker compose up -d
```

Dashboard accessible sur `https://localhost` (login : admin / voir .env)

## Documentation

- `docs/SOC_Platform_Documentation_v3.docx` — Documentation technique complète
- `docs/Playbook_IA_Proxmox_SOC.docx` — Playbook déploiement automatisé Proxmox

## Structure

```
Argus/
├── api/                    # Backend FastAPI (Python)
│   ├── core/               # Config, sécurité, auth
│   ├── models/             # Modèles Pydantic
│   ├── routers/            # Routes API (alerts, assets, rules, investigate...)
│   └── services/           # Logique métier (OpenSearch, OSINT, Wazuh...)
├── frontend/               # React + Tailwind CSS
│   └── src/
│       ├── components/     # Dashboard, AlertList, AlertDetail...
│       ├── pages/          # Investigation, AssetList, RuleList, Login
│       ├── hooks/          # useWebSocket (auth JWT)
│       └── services/       # API calls
├── nginx/                  # Config reverse proxy TLS
├── wazuh/                  # Config Wazuh Manager + règles custom
├── suricata/               # Règles Suricata + config
├── logstash/               # Pipeline Logstash
├── scripts/                # Utilitaires
├── docker-compose.yml      # Stack complète
└── .env.example            # Template variables
```

## Ports exposés

| Port | Usage |
|------|-------|
| 443 | Dashboard SOC (HTTPS) |
| 80  | Redirection HTTP → HTTPS |

Tous les services internes (OpenSearch 9200, API 8000, Redis 6379...) sont isolés dans le réseau Docker `soc-net`.

## Licence

MIT
