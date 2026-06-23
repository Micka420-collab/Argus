# 🚀 Déploiement

## Prérequis

- **Hôte** : Ubuntu 22.04 (VM Proxmox recommandée), 4 vCPU / **8 Go RAM minimum**,
  **16 Go conseillés** (et requis si le profil `ai`/Ollama est activé). Les
  `mem_limit` plafonnent OpenSearch/Logstash/Wazuh pour éviter l'OOM.
- **Docker** + **Docker Compose v2**.
- Accès réseau aux interfaces à superviser (pour Suricata en `network_mode: host`).
- `vm.max_map_count=262144` requis par OpenSearch :
  ```bash
  sudo sysctl -w vm.max_map_count=262144
  echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
  ```

## 0. Installation express (recommandée)

Un installeur guidé fait tout (Docker, secrets, certificat, options, démarrage) :

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/Micka420-collab/Argus/main/install.sh | bash
```
```powershell
# Windows (Docker Desktop)
git clone https://github.com/Micka420-collab/Argus.git ; cd Argus
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Les sections ci-dessous décrivent l'installation **manuelle** / les réglages avancés.

## 1. Cloner et configurer

```bash
git clone https://github.com/Micka420-collab/Argus.git
cd Argus
cp .env.example .env
```

Éditer `.env` (voir [CONFIGURATION.md](CONFIGURATION.md)). **Obligatoire** :

```bash
SECRET_KEY=$(openssl rand -hex 32)   # DOIT être persistant
OPENSEARCH_PASSWORD=...
REDIS_PASSWORD=...
WAZUH_API_PASSWORD=...
```

> ⚠️ `SECRET_KEY` doit être défini **et stable**. Sans valeur, l'API en génère une
> aléatoire à chaque démarrage → tous les jetons (et la clé Ed25519 du JWT PQC) changent
> à chaque redémarrage.

## 2. Certificats TLS

Aucune action requise pour démarrer : **Nginx génère un certificat auto-signé au
premier lancement** s'il est absent (CN = `SOC_DOMAIN`). En production, déposer un
vrai certificat (Let's Encrypt / interne) dans `nginx/certs/soc.crt` + `soc.key`.

> ⚠️ **Interface Suricata** : sur une VM Proxmox/Ubuntu, le NIC est souvent `ens18`
> (pas `eth0`). `install.sh` le détecte ; en manuel, fixez `NETWORK_INTERFACE` dans
> `.env` (vérifier avec `ip -br link`), sinon Suricata redémarre en boucle.

## 3. Démarrer la stack

```bash
docker compose up -d
docker compose ps        # vérifier que les services sont "healthy"
```

- Console SOC : `https://<hôte>` → page de login.
- Présentation publique : `https://<hôte>/welcome`.
- Compte admin par défaut : créé au démarrage (voir logs `soc-api` / `.env`).

## 4. Activer l'analyste IA (optionnel)

L'IA fonctionne **par défaut en mode heuristique** (aucune config). Pour un LLM :

**Ollama (local, données résidentes)**
```bash
echo "LLM_PROVIDER=ollama"      >> .env
echo "LLM_MODEL=qwen2.5:7b"     >> .env
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b
docker compose up -d soc-api
```

**Claude (API Anthropic)**
```bash
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

**Investigation autonome automatique** (sur alertes critiques) :
```bash
echo "AI_AUTO_INVESTIGATE=true" >> .env && docker compose up -d soc-api
```

## 5. Activer le TLS hybride post-quantique

Le `nginx/Dockerfile` est épinglé sur une base OpenSSL ≥ 3.5 (groupe `X25519MLKEM768`).
```bash
docker compose build nginx && docker compose up -d nginx
```
Vérifier la négociation hybride avec un client compatible (Chrome/Firefox récents).

## 6. Activer le JWT post-quantique (optionnel)

```bash
echo "PQC_JWT=true" >> .env && docker compose up -d soc-api
```
Ed25519 est actif immédiatement (dérivé de `SECRET_KEY`). Pour ajouter ML-DSA, installer
`liboqs` dans l'image (`liboqs-python` dans `api/requirements.txt`) ; les clés sont
persistées dans le volume `pqc_keys`. Statut visible via `GET /api/v1/crypto/jwt-info`.

## 7. Activer l'égress OSINT anonymisé (optionnel)

Démarrer la passerelle Tor puis pointer l'OSINT dessus :

```bash
docker compose --profile anon up -d anon-gateway
cat >> .env <<'ENV'
OSINT_ANON=true
OUTBOUND_PROXY=socks5://anon-gateway:9050
TOR_CONTROL_URL=http://anon-gateway:9052/newnym
ENV
docker compose up -d soc-api
```

**Mesh post-quantique (optionnel, Phase 3)** : monter une config WireGuard et Rosenpass
dans la passerelle pour des tunnels ML-KEM et un plan de management sans port entrant —
décommenter les `volumes` de `anon-gateway` dans `docker-compose.yml`
(`wg0.conf`, `rp.toml`) et fournir le binaire `rosenpass`.

## 8. Connecter des sources

- **Agents Wazuh** : enrôler les endpoints (ports `1514/udp`, `1515/tcp`). Restreindre par
  UFW au sous-réseau des endpoints.
- **Suricata** : définir l'interface via `NETWORK_INTERFACE` (défaut `eth0`).
- **Freebox / Threat-intel** : voir `scripts/sync_misp.py` et les clés OSINT du `.env`.

## Ports

| Port | Exposé | Usage |
|---|---|---|
| 443 | hôte | Console SOC (HTTPS) |
| 80  | hôte | Redirection → HTTPS |
| 1514/udp, 1515 | hôte (à restreindre UFW) | Agents Wazuh |
| 9200, 8000, 6379, 11434, 55000 | **interne `soc-net` uniquement** | OpenSearch, API, Redis, Ollama, Wazuh API |

## Santé & exploitation

```bash
curl -sk https://localhost/health          # {"status":"ok",...}
curl -sk https://localhost/api/v1/status   # état OpenSearch / Redis / alert engine
docker compose logs -f soc-api             # logs API
```

## Sauvegarde & restauration

Scripts fournis (sauvegardent les volumes Docker + `.env` + certificats via un
conteneur jetable, sans dépendance hôte) :

```bash
./backup.sh                          # → backups/argus-<horodatage>/
./restore.sh backups/argus-<horodatage>
```
Windows : `.\backup.ps1` / `.\restore.ps1 <dossier>`.

`backup.sh` propose d'arrêter la stack le temps de la copie (cohérence OpenSearch).
Volumes couverts : `opensearch_data`, `wazuh_etc`/`wazuh_data`/`wazuh_queue`,
`redis_data`, `pqc_keys`, `suricata_rules`. La sauvegarde contient des **secrets**
(`.env`, clés, certificats) — à stocker de façon sécurisée et hors-site.
Automatisable via cron : `0 3 * * * cd /opt/Argus && ARGUS_YES=1 ./backup.sh`.

## Mise à jour

```bash
git pull
docker compose build && docker compose up -d
```
La politique de rétention OpenSearch (ILM) est gérée automatiquement par le scheduler
(`api/core/scheduler.py`) : chaud 7 j → tiède 30 j → froid 90 j → suppression.
