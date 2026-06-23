<div align="center">

# 🛡️ Argus

### The SOC that investigates itself.

**Autonomous, post-quantum-ready Security Operations Center — self-hosted, open-source (non-commercial).**

[![License: PolyForm NC](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-0A0B0D)](LICENSE)
[![Stack](https://img.shields.io/badge/stack-FastAPI%20%C2%B7%20React%20%C2%B7%20Wazuh%20%C2%B7%20Suricata-4F8DFF)]()
[![PQC](https://img.shields.io/badge/crypto-hybrid%20ML--KEM-5EE6D3)]()
[![Status](https://img.shields.io/badge/status-active-3FB984)]()

</div>

---

Argus est une plateforme SOC **open-source auto-hébergeable** qui s'inspire des leaders du marché
(Qevlar AI, CryptoNext, Snowpack, YesWeHack) pour offrir, en une seule plateforme :

- 🤖 **Un analyste IA autonome** qui investigue chaque alerte de bout en bout et rend un verdict
  `malveillant / bénin / indéterminé` avec un rapport rédigé — **le verdict reste déterministe**,
  l'IA est *bornée* à la rédaction (inspiration **Qevlar AI**).
- ⚛️ **Une posture post-quantique** : TLS hybride X25519+ML-KEM, scanner de readiness et CBOM
  (inspiration **CryptoNext Security**).
- 🕵️ **Un égress OSINT anonymisé** via Tor/proxy pour enquêter sans s'exposer (inspiration **Snowpack**).
- 🐛 **Un module Bug Bounty / VDP** (sur la feuille de route — inspiration **YesWeHack**).

> **Licence** : source-available, **gratuit pour un usage non-commercial uniquement**
> ([PolyForm Noncommercial 1.0.0](LICENSE)). Usage commercial → nous contacter.

---

## ✨ Fonctionnalités

| Domaine | Détail |
|---|---|
| 🤖 **AI Console** | Agent d'investigation autonome (graphe déterministe : ingest → enrich → correlate → score → decide → report), persistance des rapports, **boucle de feedback analyste (RAG)** auto-améliorante |
| 🧠 **LLM borné** | Backend interchangeable : **Ollama** (local, données résidentes), **Claude**, ou **repli heuristique** (zéro dépendance). Le LLM ne décide jamais du verdict |
| 🔍 **Investigation OSINT** | AbuseIPDB · VirusTotal · RDAP · ip-api — en parallèle, avec verdict + confiance |
| ⚛️ **Post-Quantum** | TLS hybride **X25519MLKEM768**, scanner de readiness crypto-agility, **CBOM** (inventaire des handshakes TLS) |
| 📡 **Temps réel** | Alertes WebSocket sécurisées (JWT) |
| 🐛 **VDP / Bug-Bounty** | Portail de soumission, **triage assisté** (dédup + résumé IA), **scoring CVSS v3.1**, grille de récompenses, machine à états |
| 🎯 **ASM / CTEM** | Registre d'exposition **priorisé CVSS × EPSS × KEV × valeur métier** (enrichissement FIRST EPSS + CISA KEV) |
| 🗺️ **Détection** | Wazuh (SIEM/EDR) + Suricata (IDS/IPS) + règles MITRE ATT&CK |
| 🔐 **Sécurité** | Auth JWT + RBAC (admin/analyst/viewer), Nginx TLS, un seul port exposé (443) |
| 🎨 **UI « Obsidian Signal »** | Dashboard temps réel, landing de présentation, design system cohérent |

---

## 🏛️ Architecture

```
                          ┌─────────────── Nginx (TLS hybride ML-KEM, :443) ───────────────┐
   Internet / LAN  ──────▶│  → React (Argus UI)        → FastAPI (REST + WebSocket)        │
                          └───────────────────────────────────────────────────────────────┘
                                          │                         │
                 ┌────────────────────────┼─────────────────────────┼───────────────────────┐
   réseau privé  │   Wazuh Manager   OpenSearch   Redis   Ollama (IA)   Suricata (host)      │
   soc-net       │   (SIEM/EDR)      (stockage)   (cache) (LLM local)   (IDS réseau)         │
                 └──────────────────────────────────────────────────────────────────────────┘
```

| Composant | Rôle |
|-----------|------|
| **Wazuh** | SIEM / EDR — collecte et corrélation d'alertes |
| **Suricata** | IDS/IPS — détection réseau temps réel |
| **OpenSearch** | Stockage des alertes + rapports d'investigation IA |
| **FastAPI** | Backend REST + WebSocket + agent IA autonome |
| **React + Tailwind** | Dashboard & landing (design system « Obsidian Signal ») |
| **Ollama** *(opt.)* | LLM local pour l'analyste IA (données résidentes) |
| **Redis** | Cache OSINT, déduplication, sessions |
| **Nginx** | Reverse proxy TLS hybride post-quantique (seul port exposé : 443) |

---

## 🚀 Installation

### ✨ Installeur guidé (recommandé — même pour les débutants)

Il vérifie Docker, **génère tous les secrets**, crée le certificat TLS, configure
l'IA / le post-quantique / l'anonymisation selon vos réponses, démarre la stack, puis
affiche l'URL et le mot de passe admin.

**Linux / macOS** — une seule commande :

```bash
curl -fsSL https://raw.githubusercontent.com/Micka420-collab/Argus/main/install.sh | bash
```

**Windows** (PowerShell, avec Docker Desktop) :

```powershell
git clone https://github.com/Micka420-collab/Argus.git ; cd Argus
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

> Installation sans aucune question (valeurs par défaut sûres) : `ARGUS_YES=1 ./install.sh`
> (ou `.\install.ps1 -Yes`).

### 🔧 Installation manuelle

```bash
git clone https://github.com/Micka420-collab/Argus.git
cd Argus
cp .env.example .env        # éditer les secrets (SECRET_KEY, mots de passe…)
docker compose up -d
```

Dashboard : `https://localhost` · présentation publique : `https://localhost/welcome`

### 🔄 Mise à jour & 🗑️ Désinstallation

```bash
./update.sh        # met à jour (git pull + rebuild + restart), préserve données & secrets
./uninstall.sh     # arrête la stack ; propose de supprimer données/images
```
Windows : `.\update.ps1` · `.\uninstall.ps1`.

### Activer l'analyste IA (optionnel)

L'IA fonctionne **par défaut en mode heuristique** (aucune config). Pour un LLM local :

```bash
echo "LLM_PROVIDER=ollama"   >> .env
echo "LLM_MODEL=qwen2.5:7b"  >> .env
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b
# Investigation autonome auto sur alertes critiques :
echo "AI_AUTO_INVESTIGATE=true" >> .env && docker compose up -d soc-api
```

Ou via l'API Claude : `LLM_PROVIDER=claude`, `LLM_MODEL=claude-sonnet-4-6`, `ANTHROPIC_API_KEY=…`

### TLS hybride post-quantique

Actif après build de Nginx (image OpenSSL ≥ 3.5) :

```bash
docker compose build nginx && docker compose up -d nginx
```

---

## 🔌 API (extraits)

| Endpoint | Description |
|---|---|
| `GET  /api/v1/investigate/{ip}` | Investigation OSINT + verdict + analyse IA |
| `POST /api/v1/ai/investigate-ip/{ip}` | Agent autonome sur une IP |
| `POST /api/v1/ai/investigate/{alert_id}` | Agent autonome sur une alerte |
| `GET  /api/v1/ai/reports` | Rapports d'investigation autonomes |
| `POST /api/v1/ai/feedback/{id}` | Feedback analyste (corriger/valider → RAG) |
| `GET  /api/v1/crypto/readiness` | Posture post-quantique de la plateforme |
| `GET  /api/v1/crypto/inventory` | CBOM (handshakes TLS observés) |
| `POST /api/v1/vdp/reports` | Soumettre un rapport de vulnérabilité (CVSS auto) |
| `GET  /api/v1/vdp/reports` | File de triage VDP |
| `PATCH /api/v1/vdp/reports/{id}/status` | Transition d'état (triage) |
| `GET  /api/v1/vdp/cvss?vector=` | Calcul CVSS v3.1 |

---

## 📁 Structure

```
Argus/
├── api/                      # Backend FastAPI
│   ├── core/                 # config, sécurité, http (proxy-aware), scheduler
│   ├── services/             # scoring (verdict unifié), llm (borné),
│   │                         #   ai_investigation (agent autonome), feedback (RAG),
│   │                         #   crypto_inventory (CBOM), investigation OSINT…
│   └── routers/              # alerts, ai, crypto, investigate, incidents…
├── frontend/                 # React + Tailwind (design system "Obsidian Signal")
│   └── src/{components,pages,services}  # Sidebar/Topbar, AiConsole, Landing, Crypto…
├── nginx/                    # Reverse proxy TLS hybride ML-KEM
├── wazuh/ · suricata/ · logstash/   # détection & pipeline
├── docs/                     # 📚 Documentation complète (voir docs/README.md)
└── docker-compose.yml
```

---

## 📚 Documentation

Documentation technique complète dans [`docs/`](docs/README.md) :

| Doc | Contenu |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Composants, flux, les 4 piliers, structure du code |
| [Déploiement](docs/DEPLOYMENT.md) | Installation, TLS, activation IA/PQC, agents |
| [Configuration](docs/CONFIGURATION.md) | Référence des variables d'environnement |
| [API](docs/API.md) | Endpoints REST + WebSocket, rôles |
| [Sécurité](docs/SECURITY.md) | RBAC, JWT PQC, TLS hybride, durcissement |
| [Feuille de route](docs/UPGRADE_ROADMAP.md) | Phases 1 → 3 |

## 🗺️ Feuille de route

Détail complet dans [`docs/UPGRADE_ROADMAP.md`](docs/UPGRADE_ROADMAP.md).

- **✅ Livré** — verdict 3 états + analyse IA, agent autonome (graphe + RAG), scanner PQC + CBOM,
  TLS hybride, **JWT hybride post-quantique (Ed25519 + ML-DSA, repli HS256)**, égress anonymisé,
  **module VDP/Bug-Bounty (triage assisté + CVSS v3.1 + récompenses)**,
  **ASM/CTEM (priorisation CVSS × EPSS × KEV × valeur métier)**, refonte UI complète + landing.
- **✅ Aussi livré** — passerelle **anon-gateway** (Tor SOCKS + rotation NEWNYM) +
  scaffolding **mesh WireGuard+Rosenpass (PQC)**.
- **🚧 Phase 2/3** — déploiement du mesh WireGuard+Rosenpass (pairs/clés par site),
  scan actif ASM (nuclei/httpx), sync tickets (n8n), PKI mTLS interne.

---

## 🔐 Sécurité & limites assumées

- Le **verdict est déterministe** (Python) — le LLM ne fait que rédiger le rapport.
- **TLS hybride** requiert OpenSSL ≥ 3.5 ; les clients anciens retombent sur X25519.
- `SECRET_KEY` **doit** être défini et persistant (cf. `.env.example`).
- Outil **défensif** — destiné à un usage de sécurité autorisé sur votre propre infrastructure.

Vulnérabilité ? Contact responsable : **micka.delcato.rp@gmail.com**

---

## 📜 Licence

**[PolyForm Noncommercial License 1.0.0](LICENSE)** — code source-available, **libre pour tout
usage non-commercial** (perso, éducatif, recherche). Revente et usage commercial **interdits**
sans licence commerciale séparée. Contact : **micka.delcato.rp@gmail.com**.
