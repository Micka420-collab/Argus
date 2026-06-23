# 🔌 Référence API

Base : `/api/v1`. Toutes les réponses sont en JSON. La doc interactive Swagger est
disponible sur `/docs` lorsque `DEBUG=true`.

## Authentification

L'API accepte un jeton JWT de deux façons :
- En-tête `Authorization: Bearer <token>` (le frontend l'ajoute depuis `localStorage`).
- Cookie httpOnly `access_token` (même origine).

Selon `PQC_JWT`, le jeton est signé en HS256 (défaut) ou en hybride Ed25519(+ML-DSA).
Voir [SECURITY.md](SECURITY.md).

### Rôles

`admin` · `analyst` · `triager` · `researcher` · `viewer`. Matrice des permissions dans
[SECURITY.md](SECURITY.md).

| Endpoint | Méthode | Rôle | Description |
|---|---|---|---|
| `/auth/login` | POST | public | Connexion → jetons + profil. |
| `/auth/me` | GET | authentifié | Profil courant. |
| `/auth/refresh` | POST | authentifié | Renouvelle le jeton d'accès. |
| `/auth/logout` | POST | authentifié | Déconnexion. |

## Système

| Endpoint | Méthode | Description |
|---|---|---|
| `/health` | GET | État applicatif (sans auth). |
| `/api/v1/status` | GET | État OpenSearch / Redis / moteur d'alerting. |

## Alertes

| Endpoint | Méthode | Description |
|---|---|---|
| `/alerts` | GET | Recherche/liste (filtres `q, severity, status, agent_name, mitre_id, dates, page`). |
| `/alerts/stats` | GET | Agrégations dashboard (`period_hours`). |
| `/alerts/{id}` | GET / PATCH | Détail / mise à jour (statut, notes, assignation). |
| `/alerts/{id}/enrich` | POST | Enrichissement OSINT manuel. |
| `/alerts/{id}/false-positive` | POST | Marquer faux positif. |
| `/alerts/ws` | WebSocket | Flux temps réel (`?token=<jwt>`). |

## Investigation OSINT

| Endpoint | Méthode | Rôle | Description |
|---|---|---|---|
| `/investigate/{ip}` | GET | analyst | Investigation OSINT + verdict + analyse IA. `?refresh=true` ignore le cache. |

## Analyste IA autonome

| Endpoint | Méthode | Rôle | Description |
|---|---|---|---|
| `/ai/reports` | GET | analyst | Liste des investigations autonomes (`?verdict=&size=`). |
| `/ai/report/{id}` | GET | analyst | Détail (verdict, preuves, trace du graphe). |
| `/ai/investigate/{alert_id}` | POST | analyst | Lance l'agent sur une alerte. |
| `/ai/investigate-ip/{ip}` | POST | analyst | Lance l'agent sur une IP. |
| `/ai/feedback/{id}` | POST | analyst | Corriger/valider un verdict (`?corrected_verdict=&rationale=`) → RAG. |

## Posture post-quantique

| Endpoint | Méthode | Rôle | Description |
|---|---|---|---|
| `/crypto/readiness` | GET | analyst | Note de la crypto déclarée (TLS, certificat, JWT). |
| `/crypto/inventory` | GET | analyst | CBOM des handshakes TLS observés (`?period_hours=`). |
| `/crypto/jwt-info` | GET | analyst | Algorithme de signature JWT actif + clés publiques. |

## VDP / Bug-Bounty

| Endpoint | Méthode | Rôle | Description |
|---|---|---|---|
| `/vdp/reports` | POST | authentifié | Soumettre un rapport (CVSS calculé automatiquement). |
| `/vdp/reports` | GET | triager | File de triage (`?status=&size=`). |
| `/vdp/reports/{id}` | GET | triager | Détail d'un rapport. |
| `/vdp/reports/{id}/status` | PATCH | triager | Transition d'état (machine à états validée). |
| `/vdp/programs` | GET | authentifié | Programmes (crée un défaut si vide). |
| `/vdp/programs` | POST | admin | Créer un programme. |
| `/vdp/cvss` | GET | authentifié | Calcul CVSS v3.1 (`?vector=CVSS:3.1/...`). |
| `/vdp/stats` | GET | triager | Compteurs par statut/sévérité. |

## ASM / CTEM (surface d'exposition)

| Endpoint | Méthode | Rôle | Description |
|---|---|---|---|
| `/exposure/findings` | GET | analyst | Findings priorisés (`?tier=&status=&size=`), triés par score. |
| `/exposure/findings` | POST | analyst | Ajouter un finding (enrichi EPSS/KEV + priorisé). |
| `/exposure/findings/{id}/status` | PATCH | analyst | Changer le statut (open/triaged/mitigated/accepted/false_positive). |
| `/exposure/assets` | GET/POST | analyst | Inventaire des assets exposés (valeur métier). |
| `/exposure/cve/{cve}` | GET | analyst | Enrichissement EPSS + KEV d'un CVE. |
| `/exposure/stats` | GET | analyst | Compteurs (total, ouverts, KEV, par tier). |

Priorisation : `score = (0.5·CVSS/10 + 0.5·exploit) × valeur_métier`, où
`exploit = 1.0 si KEV sinon EPSS` ; un finding KEV (activement exploité) reçoit un
plancher de priorité **critique**.

## Incidents · Assets · Règles · Playbooks

| Endpoint | Méthode | Description |
|---|---|---|
| `/incidents` | GET/POST | Liste / création. |
| `/incidents/{id}` | GET/PATCH/DELETE | Détail / màj / suppression. |
| `/incidents/{id}/notes` | POST | Ajouter une note. |
| `/incidents/{id}/alerts/{alertId}` | POST | Lier une alerte. |
| `/assets` | GET/POST | Inventaire des assets. |
| `/assets/{id}` | GET/PATCH/DELETE | Détail / màj / suppression. |
| `/assets/{id}/maintenance` | POST | Bascule mode maintenance. |
| `/rules` | GET | Règles Wazuh (tags MITRE). |
| `/playbooks` | GET | Playbooks disponibles. |
| `/playbooks/run` | POST | Exécuter un playbook. |
| `/playbooks/confirm-isolation/{alertId}` | POST | Confirmer une isolation réseau. |
| `/playbooks/block-ip` | POST | Bloquer une IP (`?ip=`). |

## Exemple

```bash
# Calcul CVSS
curl -sk "https://localhost/api/v1/vdp/cvss?vector=CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" \
  -H "Authorization: Bearer $TOKEN"
# → {"vector":"...","score":9.8,"severity":"critical"}

# Investigation IA d'une IP
curl -sk -X POST "https://localhost/api/v1/ai/investigate-ip/203.0.113.7" \
  -H "Authorization: Bearer $TOKEN"
```
