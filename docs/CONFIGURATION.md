# ⚙️ Configuration

Toutes les variables sont chargées via Pydantic Settings (`api/core/config.py`) depuis
l'environnement (ou un fichier `.env`). Modèle : [`.env.example`](../.env.example).

## Application

| Variable | Défaut | Description |
|---|---|---|
| `SECRET_KEY` | *(aléatoire)* | **Obligatoire & persistant.** Clé de signature HS256 et graine Ed25519 du JWT PQC. `openssl rand -hex 32`. |
| `ENVIRONMENT` | `production` | `development` \| `staging` \| `production`. |
| `DEBUG` | `false` | Active Swagger (`/docs`) et les logs DEBUG. |
| `CORS_ORIGINS` | localhost… | Origines autorisées pour le frontend. |

## OpenSearch

| Variable | Défaut | Description |
|---|---|---|
| `OPENSEARCH_URL` | `https://opensearch:9200` | Endpoint. |
| `OPENSEARCH_USER` / `OPENSEARCH_PASSWORD` | `admin` / — | Identifiants. |
| `OPENSEARCH_INDEX_ALERTS` | `wazuh-alerts-*` | Index des alertes Wazuh. |
| `OPENSEARCH_INDEX_SURICATA` | `soc-suricata-*` | Index des événements Suricata. |
| `OPENSEARCH_INDEX_AI` | `soc-investigations` | Rapports de l'agent IA. |
| `OPENSEARCH_INDEX_VDP` | `soc-vdp-reports` | Rapports VDP / bug-bounty. |
| `OPENSEARCH_INDEX_EXPOSURE` | `soc-exposure` | ASM/CTEM (assets + findings). |

## Wazuh / Redis

| Variable | Défaut | Description |
|---|---|---|
| `WAZUH_API_URL` | `https://wazuh-manager:55000` | API Wazuh (Active Response). |
| `WAZUH_API_USER` / `WAZUH_API_PASSWORD` | `wazuh-wui` / — | Identifiants API Wazuh. |
| `REDIS_URL` | `redis://redis:6379` | Endpoint Redis. |
| `REDIS_PASSWORD` | — | Mot de passe Redis. |

## Alerting & enrichissement

| Variable | Défaut | Description |
|---|---|---|
| `ALERT_MIN_LEVEL` | `10` | Niveau Wazuh minimum pour alerter. |
| `ALERT_CRITICAL_LEVEL` | `14` | Niveau d'alerte immédiate (+ déclenche l'IA auto). |
| `DEDUP_WINDOW_MINUTES` | `10` | Fenêtre de déduplication. |
| `GROUP_FLUSH_SECONDS` | `30` | Intervalle d'envoi des alertes groupées. |
| `POLL_INTERVAL_SECONDS` | `15` | Intervalle de polling OpenSearch. |
| `ENRICH_RISK_THRESHOLD` | `90` | Score déclenchant une escalade auto. |
| `ENRICH_CACHE_TTL` | `3600` | TTL du cache d'enrichissement (s). |

## Threat-intel (OSINT)

| Variable | Défaut | Description |
|---|---|---|
| `ABUSEIPDB_KEY` | — | Clé AbuseIPDB (compte gratuit). |
| `VIRUSTOTAL_KEY` | — | Clé VirusTotal (compte gratuit). |
| `MISP_URL` / `MISP_KEY` | — | Instance MISP (optionnel). |

## Notifications

| Variable | Description |
|---|---|
| `PUSHOVER_TOKEN` / `PUSHOVER_USER` | Pushover. |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram. |
| `DISCORD_WEBHOOK` | Webhook Discord. |

## Analyste IA (pilier Qevlar)

| Variable | Défaut | Description |
|---|---|---|
| `LLM_PROVIDER` | `none` | `none` (heuristique) \| `ollama` \| `claude`. |
| `LLM_BASE_URL` | `http://ollama:11434` | Endpoint Ollama. |
| `LLM_MODEL` | — | ex. `qwen2.5:7b`, `claude-sonnet-4-6`. |
| `LLM_TIMEOUT` | `60` | Timeout des appels LLM (s). |
| `ANTHROPIC_API_KEY` | — | Requis si `LLM_PROVIDER=claude`. |
| `AI_AUTO_INVESTIGATE` | `false` | Déclenche l'agent autonome sur alertes critiques. |

## Égress anonymisé (pilier Snowpack)

| Variable | Défaut | Description |
|---|---|---|
| `OSINT_ANON` | `false` | Route l'OSINT par `OUTBOUND_PROXY`. |
| `OUTBOUND_PROXY` | — | ex. `socks5://anon-gateway:9050` (nécessite `httpx[socks]`). |
| `TOR_CONTROL_URL` | — | Endpoint HTTP de rotation d'identité (NEWNYM). |

## Post-quantique (pilier CryptoNext)

| Variable | Défaut | Description |
|---|---|---|
| `JWT_ALGORITHM` | `HS256` | Algorithme JWT classique (si `PQC_JWT=false`). |
| `PQC_JWT` | `false` | Active le JWT hybride Ed25519 (+ ML-DSA si liboqs). |
| `PQC_KEYS_DIR` | `/var/lib/argus/pqc` | Persistance des clés ML-DSA. |
| `TLS_GROUPS` | `X25519MLKEM768:X25519:secp256r1` | Groupes d'échange TLS (référence readiness). |
| `TLS_CERT_SIG` | `RSA-4096` | Type de signature du certificat (référence readiness). |

## Réseau / divers

| Variable | Défaut | Description |
|---|---|---|
| `SOC_DOMAIN` | `soc.lan` | Domaine de la console. |
| `NETWORK_INTERFACE` | `eth0` | Interface écoutée par Suricata. |
