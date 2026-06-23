# 🛡️ Argus — Feuille de route : SOC autonome & prêt post-quantique

Évolution d'Argus vers une plateforme **SOC autonome, auto-hébergée et résistante
au quantique**, en s'inspirant de quatre acteurs et en les recréant en
**open-source** :

| Inspiration | Apport | Pilier Argus |
|---|---|---|
| **Qevlar AI** | Investigation autonome des alertes, fin de la fatigue d'alerte, verdict malveillant/bénin, rapport d'enquête | **A — Analyste IA autonome** |
| **CryptoNext Security** | Cryptographie post-quantique (ML-KEM, ML-DSA), crypto-agilité, inventaire (CBOM) | **B — Posture post-quantique** |
| **Snowpack** | Réseau zero-trust « invisible », égress multi-chemin, anonymisation | **C — Protection réseau PQC** |
| **YesWeHack** | Bug bounty / VDP, triage, scoring CVSS, grille de récompenses | **D — Module VDP / exposure** |

> Principe directeur (cœur de Qevlar) : **le verdict est déterministe (Python pur)** ;
> le **LLM est borné** à la rédaction du rapport — il ne décide jamais.

---

## ✅ Livré dans cette itération (increment 1)

### Pilier A — Analyste IA autonome (fondations)
- `api/services/scoring.py` — **scorer de verdict unifié** : `compute_verdict(Evidence)`
  → score 0-100 + **verdict 3 états** (`malicious|benign|inconclusive`) + **confiance**.
  Remplace les deux scorers divergents (`investigation._assess_risk` &
  `enrichment._compute_risk`) par une source de vérité unique.
- `api/services/llm.py` — **adaptateur LLM borné** : backends `ollama` (local,
  données résidentes) / `claude` (API Anthropic) / repli **heuristique** déterministe
  (zéro dépendance, marche toujours). Imports paresseux.
- `api/services/investigation.py` — l'investigation OSINT renvoie désormais le
  **verdict** + une **analyse IA** rédigée (`ai.summary`, `ai.narrative`,
  `ai.recommended_actions`).
- `frontend/src/pages/Investigation.jsx` — **badge de verdict** + panneau
  **« Analyse IA »** + bouton **Ré-analyser**.

### Pilier B — Posture post-quantique
- `api/services/crypto_inventory.py` + `api/routers/crypto.py` — **scanner de
  readiness PQC** (auto-évaluation crypto-agility) + **CBOM** observé (handshakes
  TLS Suricata) avec classification quantum-safe / hybride / vulnérable.
- `frontend/src/pages/Crypto.jsx` — page **Post-Quantum** (jauge de readiness,
  composants notés, CBOM).
- `nginx/nginx.conf` + `nginx/Dockerfile` — **TLS hybride X25519+ML-KEM768**
  (OpenSSL ≥ 3.5 via `nginx:1.29-alpine`).

### Pilier C — Égress anonymisé (fondation)
- `api/core/http.py` — client HTTP sortant **partagé et proxy-aware**
  (`OUTBOUND_PROXY` / Tor) ; tout l'OSINT (`investigation.py`, `enrichment.py`)
  passe par lui.

### Corrections de bugs intégrées
- `routers/investigation.py` : `_user.username` (AttributeError sur un dict) →
  `_user.get("username")`.
- `.env.example` : `JWT_SECRET` (mort) → **`SECRET_KEY`** + avertissement de
  persistance (sinon jetons invalidés à chaque redémarrage).
- Déduplication du scorer de risque.

### Infra
- `docker-compose.yml` : service **`ollama`** (profil `ai`) + câblage des variables
  LLM / proxy / PQC dans `soc-api`.

---

## 🚧 Phase 2 — Autonomie complète, auth PQC, VDP

### Pilier A
- `api/services/ai_investigation.py` — **agent LangGraph** : graphe typé
  `ingest → normalize(LLM) → enrich → correlate → score → decide → report`.
  Branché dans `AlertEngine._process_alert` (drapeau `AI_AUTO_INVESTIGATE`) ;
  persistance dans OpenSearch `soc-investigations-*` ; progression live via un
  `useAiStream.js` cloné de `useWebSocket.js`.
- `api/services/feedback.py` — **RAG d'apprentissage** : surcharge analyste +
  justification stockées en embeddings (pgvector), réinjectées dans les analyses
  futures (auto-amélioration sans fine-tuning).
- `api/routers/ai.py` — `POST /ai/investigate/{alert_id}`, `GET /ai/report/{id}`,
  `POST /ai/feedback/{id}`.

### Pilier B
- `api/core/pqc.py` + wrap de `core/security.py` — **JWT hybride Ed25519 + ML-DSA-65**
  (`PQC_JWT=true`) ; **fix SECRET_KEY persistante**. `liboqs-python` dans `api/Dockerfile`.
- `api/services/crypto_policy.py` + conteneur **OPA** — politique Rego
  (algos/tailles/hybride obligatoire) évaluée sur le CBOM ; violations → alertes.
- `wazuh/rules/local_rules.xml` — détections downgrade TLS / handshake non-hybride
  (IDs `100100+`).

### Pilier C
- `anon-gateway/` — conteneur **WireGuard + Rosenpass (ML-KEM) + Tor + obfs4** :
  plan de management **sans port entrant** (propriété « serveur invisible »).
- `frontend/src/pages/Anonymity.jsx` — santé des circuits, bouton « nouvelle
  identité Tor », statut d'égress.

### Pilier D — Bug bounty / VDP
- `api/models/vdp.py`, `api/services/vdp.py`, `api/services/vdp_triage.py`,
  `api/routers/vdp.py` — programmes, scopes, rapports (machine à états),
  **scoring CVSS** (`cvss`), **triage IA** (dédup par embeddings + extraction LLM),
  grille de récompenses.
- `core/security.py` : rôles `RESEARCHER` / `TRIAGER`.
- `frontend/src/pages/Vdp.jsx` + `VdpSubmit.jsx` — portail de soumission + file de
  triage.
- **Postgres (pgvector)** pour le modèle relationnel programme→scope→rapport→récompense.

---

## 🔭 Phase 3 — Profondeur & durcissement
- Graphe IA : nœuds **Velociraptor** (collecte endpoint), **RITA/Zeek** (beaconing C2),
  **Sigma/PyOD** (anomalies) ; `action_ai_decide` avec garde humaine.
- **ASM/CTEM** : conteneur `asm-worker` (subfinder/dnsx/naabu/httpx/nuclei) +
  `exposure.py` ; priorisation `CVSS × EPSS × KEV × valeur métier`.
- **PKI PQC interne** : `step-ca` + mTLS ML-DSA entre services (retirer
  `verify=False`).
- Synchronisation tickets (**n8n** → Jira/GitLab/GitHub).
- Migration Redis → Postgres (incidents/assets/users/audit).

---

## ⚙️ Activer les nouveautés

```bash
# 1. Verdict + IA (repli heuristique par défaut, aucune config requise)
#    -> déjà actif : ouvrir une investigation, voir le badge de verdict + l'analyse.

# 2. IA locale (Ollama) :
echo "LLM_PROVIDER=ollama"      >> .env
echo "LLM_MODEL=qwen2.5:7b"     >> .env
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b

# 2b. ou IA via Claude :
#   LLM_PROVIDER=claude / LLM_MODEL=claude-sonnet-4-6 / ANTHROPIC_API_KEY=...

# 3. Posture post-quantique : onglet "Post-Quantum" du dashboard.
#    TLS hybride actif après rebuild nginx (OpenSSL 3.5) :
docker compose build nginx && docker compose up -d nginx

# 4. Égress OSINT anonymisé (nécessite un proxy Tor) :
#   OSINT_ANON=true / OUTBOUND_PROXY=socks5://anon-gateway:9050
```

---

## 🔐 Limites assumées (honnêteté open-source)
- **TLS hybride** : nécessite OpenSSL ≥ 3.5. Les clients anciens retombent sur X25519.
- **JWT PQC** : `liboqs` natif requis (Phase 2) ; HS256 (symétrique) reste
  quantum-résistant en attendant.
- **Snowpack** : l'overlay OTP information-théorique n'est pas reproductible tel quel ;
  l'équivalent OSS (WireGuard+Rosenpass+Tor) couvre la valeur défensive (zéro port
  entrant, tunnels PQC, OSINT anonymisé), pas la propriété théorique.
- **LLM** : borné par conception — il ne calcule jamais le verdict, il l'explique.
