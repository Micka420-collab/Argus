# 📚 Documentation Argus

Documentation technique de **Argus** — SOC autonome et post-quantique, auto-hébergé.
Version applicative : **v3.0.0**.

> Argus est *le SOC qui s'investigue lui-même* : il trie et investigue chaque alerte de
> façon autonome (verdict + rapport), assure une posture cryptographique post-quantique,
> anonymise son OSINT, et intègre un module bug-bounty/VDP — le tout en open-source
> (licence non-commerciale).

## Sommaire

| Document | Contenu |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Vision, composants, flux de données, les 4 piliers, structure du code |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Prérequis, installation Docker/Proxmox, TLS, activation IA/PQC, agents |
| [CONFIGURATION.md](CONFIGURATION.md) | Référence exhaustive des variables d'environnement |
| [API.md](API.md) | Référence de l'API REST + WebSocket, authentification, rôles |
| [SECURITY.md](SECURITY.md) | Auth/RBAC, JWT post-quantique, TLS hybride, égress anonymisé, durcissement |
| [UPGRADE_ROADMAP.md](UPGRADE_ROADMAP.md) | Feuille de route 4 piliers (livré / phases 2-3) |

## Démarrage express

```bash
git clone https://github.com/Micka420-collab/Argus.git
cd Argus
cp .env.example .env        # renseigner SECRET_KEY + mots de passe
docker compose up -d
```

- Console SOC : `https://localhost`
- Page de présentation publique : `https://localhost/welcome`

Voir [DEPLOYMENT.md](DEPLOYMENT.md) pour le détail (TLS, IA locale, PQC, agents Wazuh, Suricata).

## Conventions

- **Langue** : interface et documentation en français ; identifiants techniques en anglais.
- **Sécurité** : un seul port exposé (443). Tous les services internes restent sur le
  réseau Docker privé `soc-net`.
- **Principe IA** : le **verdict est déterministe** (Python) ; le **LLM est borné** à la
  rédaction du rapport — il ne décide jamais.
