# 🔐 Sécurité

## Surface d'exposition

- **Un seul point d'entrée** : Nginx sur `:443` (+ `:80` en redirection). Tous les services
  internes (OpenSearch, API, Redis, Ollama, Wazuh API) restent sur le réseau Docker privé
  `soc-net` (`172.20.0.0/24`) et **ne sont jamais exposés** sur l'hôte.
- Ports agents Wazuh (`1514/udp`, `1515`) — à restreindre par UFW au sous-réseau des endpoints.
- En-têtes durcis (Nginx) : HSTS, CSP, `X-Frame-Options: DENY`, `X-Content-Type-Options`,
  `Referrer-Policy`, `Permissions-Policy`. Rate-limiting global + anti-bruteforce login.

## Authentification & RBAC

JWT + RBAC (`api/core/security.py`). Identité gérée via `api/services/users.py`.

| Rôle | read | write | triage | submit | delete | admin |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| `admin` | ✓ | ✓ | ✓ | | ✓ | ✓ |
| `analyst` | ✓ | ✓ | ✓ | | | |
| `triager` | ✓ | | ✓ | | | |
| `researcher` | ✓ | | | ✓ | | |
| `viewer` | ✓ | | | | | |

Dépendances FastAPI : `require_analyst`, `require_triager`, `require_admin`. Le jeton est
accepté via en-tête `Bearer` ou cookie httpOnly (même origine).

## JWT — classique vs post-quantique

| | `PQC_JWT=false` (défaut) | `PQC_JWT=true` |
|---|---|---|
| Algorithme | HS256 (HMAC symétrique) | Ed25519 (+ ML-DSA-65 si liboqs) |
| Résistance quantique | ✓ (symétrique, Grover seulement) | ✓ asymétrique post-quantique |
| Clé | `SECRET_KEY` | Ed25519 **dérivé de `SECRET_KEY`** (déterministe, stable) + ML-DSA persistée |
| Vérifiabilité externe | non (secret partagé) | oui (clé publique via `/crypto/jwt-info`) |

`api/core/pqc.py` produit un jeton compact *detached-JWS* ; la vérification exige Ed25519
et, en plus, ML-DSA lorsqu'il est présent. Tester : round-trip, falsification, expiration.

> **Bug corrigé** : auparavant `SECRET_KEY` était régénéré à chaque process (jetons
> invalidés au redémarrage, multi-worker cassé). Il doit désormais être défini et persistant.

## Cryptographie post-quantique

- **Transport** : TLS 1.3 hybride `X25519MLKEM768` (X25519 + ML-KEM-768, FIPS 203) au niveau
  Nginx. Protège contre « harvest-now, decrypt-later ». Repli X25519 pour clients anciens.
- **Authentification** : voir ci-dessus.
- **Gouvernance** : `/crypto/readiness` note la posture ; `/crypto/inventory` (CBOM) classe
  les handshakes observés (sûr / hybride / vulnérable). Modèle de menace dans
  `api/services/crypto_inventory.py`.

## Égress anonymisé (OSINT)

Avec `OSINT_ANON=true` + `OUTBOUND_PROXY`, toutes les requêtes threat-intel sortent par
Tor/proxy (`api/core/http.py`) → l'IP réelle du SOC n'est pas « marquée » par les
fournisseurs de réputation, et les IPs investiguées ne sont pas divulguées.

## IA — garde-fous

- Le **verdict est déterministe** (`api/services/scoring.py`). Le **LLM ne décide jamais** ;
  il est borné à la rédaction (`api/services/llm.py`).
- Les **actions destructrices** (blocage IP, isolation réseau) ne sont **jamais exécutées
  automatiquement** par l'agent : elles sont proposées avec `requires_confirmation=true`
  (human-in-the-loop). Cf. `api/services/ai_investigation.py`, `api/services/playbooks.py`.
- Si `LLM_PROVIDER=ollama`, les données restent résidentes (aucun appel cloud).

## Secrets & journalisation

- Secrets dans `.env` (hors Git ; `.gitignore` exclut `.env`, `*.key`, `*.crt`…).
- Journal d'audit des mutations (POST/PATCH/DELETE) via `api/middleware/security.py` et
  `api/services/audit.py`.

## Checklist de durcissement (production)

- [ ] `SECRET_KEY` fort et persistant ; mots de passe OpenSearch/Redis/Wazuh changés.
- [ ] `DEBUG=false` (Swagger désactivé).
- [ ] Certificat TLS valide (remplacer l'auto-signé) ; envisager `PQC_JWT=true`.
- [ ] UFW : restreindre `1514/1515` au sous-réseau des endpoints.
- [ ] Restreindre `CORS_ORIGINS` au domaine réel.
- [ ] Sauvegardes chiffrées des volumes (cf. [DEPLOYMENT.md](DEPLOYMENT.md)).
- [ ] *(Phase 3)* mTLS interne entre services, mesh WireGuard pour le plan de management.

## Divulgation responsable

Vulnérabilité dans Argus ? Contact : **micka.delcato.rp@gmail.com**. Le module VDP intégré
(`/vdp`) peut aussi servir de canal de soumission.

## Usage autorisé

Argus est un outil **défensif**, destiné à la surveillance de votre **propre**
infrastructure (ou avec autorisation explicite). Licence non-commerciale — voir
[`LICENSE`](../LICENSE).
