# 🏛️ Architecture

## Vision

Argus unifie quatre capacités, chacune inspirée d'un acteur du marché, en une seule
plateforme open-source auto-hébergée :

| Pilier | Inspiration | Capacité |
|---|---|---|
| **A** | Qevlar AI | Analyste IA autonome — investigation de bout en bout, verdict, rapport |
| **B** | CryptoNext | Posture post-quantique — TLS hybride ML-KEM, JWT hybride ML-DSA, CBOM |
| **C** | Snowpack | Réseau anonymisé — égress OSINT via Tor/proxy |
| **D** | YesWeHack | Bug-bounty / VDP — soumission, triage, CVSS, récompenses |

## Vue d'ensemble

```
                 ┌──────────── Nginx (TLS hybride X25519+ML-KEM, :443) ───────────┐
  Internet/LAN ─▶│  /            → React (UI Argus + landing /welcome)            │
                 │  /api/*       → FastAPI (REST)                                  │
                 │  /api/v1/alerts/ws → WebSocket (alertes temps réel, JWT)        │
                 └────────────────────────────────────────────────────────────────┘
                                         │
        ┌────────────────────────────────┼─────────────────────────────────────────┐
        │  Réseau Docker privé soc-net (172.20.0.0/24) — aucun port hôte exposé      │
        │                                                                            │
        │  FastAPI ──┬─ OpenSearch  (alertes, investigations IA, rapports VDP, CBOM) │
        │            ├─ Redis       (cache OSINT, déduplication, maintenance)        │
        │            ├─ Wazuh Mgr   (SIEM/EDR, Active Response)                       │
        │            ├─ Ollama      (LLM local, profil « ai », optionnel)            │
        │            └─ égress ────▶ OSINT (AbuseIPDB/VT/RDAP) via proxy/Tor optionnel│
        │                                                                            │
        │  Suricata (network_mode: host) ─▶ Logstash ─▶ OpenSearch                   │
        └────────────────────────────────────────────────────────────────────────────┘
```

## Composants

| Service | Image / techno | Rôle |
|---|---|---|
| `nginx` | nginx 1.29-alpine (OpenSSL ≥ 3.5) | Reverse proxy TLS hybride PQC, seul point d'entrée |
| `soc-frontend` | React 18 + Tailwind | UI « Obsidian Signal » + landing |
| `soc-api` | FastAPI (Python 3.12) | REST, WebSocket, moteur d'alerting, agent IA |
| `opensearch` | OpenSearch 2.11 | Stockage & recherche (alertes + données Argus) |
| `wazuh-manager` | Wazuh 4.7 | SIEM/EDR, corrélation, Active Response |
| `suricata` | jasonish/suricata | IDS/IPS réseau (host) |
| `logstash` | Logstash OSS | Normalisation/enrichissement du pipeline |
| `redis` | redis 7-alpine | Cache, déduplication, sessions |
| `ollama` | ollama/ollama (profil `ai`) | LLM local pour l'analyste IA |

## Flux de traitement d'une alerte

```
Wazuh/Suricata → OpenSearch
        │
        ▼  (polling 15s — AlertEngine)
1. Maintenance ? ──▶ ignorée si asset en maintenance
2. Déduplication (Redis, fenêtre 10 min)
3. Enrichissement IP (AbuseIPDB + VirusTotal, async) → scorer unifié
4. Playbooks MITRE (block IP, isolation… actions irréversibles human-gated)
5a. Niveau ≥ 14 (critique) ──▶ notification immédiate + broadcast WebSocket
5b. Sinon ──▶ groupement + notification périodique (30s)
3bis. Si AI_AUTO_INVESTIGATE ──▶ agent IA autonome (cf. pilier A)
```

Code clé : `api/services/alerting.py` (`AlertEngine._process_alert`),
`api/services/opensearch.py`, `api/services/enrichment.py`, `api/services/playbooks.py`.

## Pilier A — Analyste IA autonome

Graphe d'investigation **déterministe** (style LangGraph, sans dépendance lourde). Chaque
nœud enrichit un état partagé et journalise une trace auditable.

```
ingest → enrich(OSINT) → correlate(OpenSearch, beaconing) → retrieve_feedback(RAG)
       → score(déterministe) → decide → report(LLM borné)
       → propose_actions(human-gated) → persist → escalate
```

- **Verdict** : `malicious | benign | inconclusive` + confiance, calculé par
  `api/services/scoring.py` (`compute_verdict`) — **source de vérité unique**.
- **LLM borné** : `api/services/llm.py` (Ollama / Claude / repli heuristique) — rédige
  uniquement le récit et la remédiation.
- **RAG** : `api/services/feedback.py` — les corrections analyste sont stockées puis
  réinjectées dans les investigations similaires (auto-amélioration sans fine-tuning).
- **Agent** : `api/services/ai_investigation.py` ; rapports persistés dans
  `soc-investigations` ; API `api/routers/ai.py` ; UI `frontend/src/pages/AiConsole.jsx`.

## Pilier B — Posture post-quantique

- **Transport** : TLS hybride `X25519MLKEM768` au niveau Nginx (`nginx/nginx.conf`,
  `ssl_ecdh_curve`). Repli automatique X25519 pour les clients anciens.
- **Authentification** : JWT hybride **Ed25519 + ML-DSA** (`api/core/pqc.py`), activé par
  `PQC_JWT=true` ; repli HS256 par défaut.
- **Gouvernance** : scanner de readiness + **CBOM** (`api/services/crypto_inventory.py`,
  `api/routers/crypto.py`) classant chaque algorithme (sûr / hybride / vulnérable) ;
  UI `frontend/src/pages/Crypto.jsx`.

## Pilier C — Réseau anonymisé

- Client HTTP sortant partagé et proxy-aware (`api/core/http.py`). Quand `OSINT_ANON=true`
  et `OUTBOUND_PROXY` défini, tout l'OSINT sort par Tor/proxy → l'IP réelle du SOC n'est
  pas « marquée » par les fournisseurs de réputation.
- *Phase 3* : overlay maillé WireGuard + Rosenpass (plan de management sans port entrant).

## Pilier D — VDP / Bug-Bounty

- Modèles & machine à états : `api/models/vdp.py`.
- Service : `api/services/vdp.py` — **calculateur CVSS v3.1** maison, grille de
  récompenses, transitions validées, stockage `soc-vdp-reports`.
- Triage assisté : `api/services/vdp_triage.py` — détection de doublon + résumé LLM.
- API : `api/routers/vdp.py` ; rôles `researcher` / `triager` ; UI `frontend/src/pages/Vdp.jsx`.

### Extension — Gestion d'exposition (ASM / CTEM)

Registre d'exposition priorisé par **exposition réelle** : `CVSS × EPSS × KEV ×
valeur métier`. EPSS (FIRST.org) = probabilité d'exploitation ; KEV (CISA) =
activement exploité (plancher de priorité critique). Code : `api/models/exposure.py`,
`api/services/exposure.py` (`compute_priority`, enrichissement EPSS/KEV avec cache
Redis), `api/routers/exposure.py` ; stockage `soc-exposure-{assets,findings}` ;
UI `frontend/src/pages/Exposure.jsx`. Le scan actif (nuclei/httpx…) est un point
d'intégration externe (`source="scan"`).

## Stockage

| Données | Backend | Index / clé |
|---|---|---|
| Alertes Wazuh | OpenSearch | `wazuh-alerts-*` |
| Événements Suricata | OpenSearch | `soc-suricata-*` |
| Investigations IA | OpenSearch | `soc-investigations` |
| Feedback analyste (RAG) | OpenSearch | `soc-ai-feedback` |
| Rapports VDP | OpenSearch | `soc-vdp-reports` (+ `-programs`) |
| Exposition ASM/CTEM | OpenSearch | `soc-exposure-assets` / `soc-exposure-findings` |
| Cache OSINT / dédup / maintenance | Redis | `enrich:*`, `dedup:*`, `maintenance:*`, `investigation:*` |
| Clés ML-DSA (JWT PQC) | Volume | `PQC_KEYS_DIR` |

## Structure du dépôt

```
api/
├── core/        config.py · security.py · pqc.py · http.py · scheduler.py
├── models/      alert.py · asset.py · incident.py · user.py · vdp.py
├── routers/     auth · alerts · incidents · assets · rules · playbooks
│                investigation · ai · crypto · vdp
├── services/    opensearch · alerting · enrichment · deduplication · notifications
│                investigation · scoring · llm · ai_investigation · feedback
│                crypto_inventory · vdp · vdp_triage · playbooks · audit · users
└── middleware/  security.py (headers, rate-limit, audit)

frontend/src/
├── components/  Sidebar · Topbar · ui (kit) · Dashboard · AlertList · …
├── pages/       Landing · Login · AiConsole · Vdp · Crypto · Investigation · …
├── contexts/    AuthContext
├── hooks/       useWebSocket
└── services/    api.js (clients groupés)
```
