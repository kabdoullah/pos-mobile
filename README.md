# POS Mobile

Application de point de vente mobile pour les PME en Côte d'Ivoire.

## Vision

Permettre aux commerçants de quartier (alimentation, cosmétique, téléphonie) de digitaliser leurs encaissements à moindre coût via un smartphone Android, sans matériel coûteux.

## Statut

MVP en développement, mode solo. Hypothèse à valider : adoption quotidienne par les commerçants sur 30-60 jours.

## Stack

| Couche | Technologie                                    |
|---|------------------------------------------------|
| Backend | FastAPI 0.115+ / Python 3.12+ (gérée par `uv`) |
| Base de données | PostgreSQL 17 avec Row-Level Security          |
| ORM / Migrations | SQLAlchemy 2.0 async / Alembic                 |
| Mobile | Flutter 3.22+ (Android d'abord)                |
| Storage local | drift (SQLite typé)                            |
| State management | Riverpod 3                                     |
| Code formatter / linter | ruff (Python) / dart format (Dart)             |
| Email | Brevo SMTP (offre gratuite)                    |
| Hébergement | VPS Hetzner + Docker Compose + Caddy           |
| Assistant IA | Claude Code (config dans `.claude/`)           |

## Démarrage rapide

### Prérequis

- Docker + Docker Compose
- `uv` (Python package manager) : `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Flutter SDK 3.22+
- Node.js 18+ (pour Claude Code)

### Lancer le backend en local

```bash
cd backend
cp .env.example .env
# Générer un JWT secret :
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Le coller dans .env

# Lancer Postgres
docker compose up -d postgres

# Installer les deps + lancer le serveur
make install
make migrate
make dev
```

API disponible sur http://localhost:8000, doc Swagger sur http://localhost:8000/docs.

### Lancer l'app Flutter

```bash
cd mobile
make install
make gen          # générer le code (drift, freezed, riverpod, retrofit)
make run          # lancer sur émulateur Android (avec backend en local)
```

### Configurer Claude Code (recommandé pour solo dev)

```bash
# Installer
npm install -g @anthropic-ai/claude-code

# Lancer dans le projet
cd pos-mobile-ci
claude
```

La config est dans `.claude/`. Voir `.claude/README.md` pour le détail.

## Structure du repo

```
pos-mobile/
├── README.md                    Ce fichier
├── CLAUDE.md                    Instructions globales pour Claude Code
├── .gitignore
├── .pre-commit-config.yaml
├── docker-compose.yml           Postgres + API + Caddy
├── Caddyfile                    Reverse proxy pour la prod
├── .claude/                     Config Claude Code
│   ├── README.md
│   ├── settings.json
│   ├── rules/                   Règles contextuelles (path-scoped)
│   ├── commands/                Slash commands
│   └── hooks/                   Scripts auto-format et anti-destruction
├── backend/                     API FastAPI
│   ├── README.md
│   ├── pyproject.toml           uv + ruff + pytest + mypy
│   ├── Dockerfile
│   ├── Makefile
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   └── modules/             auth, stores, catalog, sales, sync
│   ├── alembic/
│   └── tests/
├── mobile/                      App Flutter
│   ├── README.md
│   ├── pubspec.yaml
│   ├── analysis_options.yaml
│   ├── Makefile
│   ├── lib/
│   │   ├── main.dart
│   │   ├── core/
│   │   ├── features/            auth, catalog, sales, printing, sync
│   │   ├── shared/
│   │   └── database/
│   └── test/
├── docs/                        Documentation technique
│   ├── architecture.md
│   ├── data-model.md
│   ├── api.md
│   ├── runbook.md
│   └── adr/                     6 ADRs structurants
└── scripts/                     Scripts ops (à venir)
```

## Documentation

- **Architecture globale** : [docs/architecture.md](docs/architecture.md)
- **Modèle de données** : [docs/data-model.md](docs/data-model.md)
- **API** : [docs/api.md](docs/api.md)
- **Runbook ops** : [docs/runbook.md](docs/runbook.md)
- **ADRs** : [docs/adr/](docs/adr/)

## Conventions

- **Conventional Commits** pour les messages de commit (`feat:`, `fix:`, `refactor:`, etc.)
- **PEP 8 + ruff** pour Python (config dans `backend/pyproject.toml`)
- **flutter_lints stricts** pour Dart (config dans `mobile/analysis_options.yaml`)
- **Pre-commit hooks** activés (`pip install pre-commit && pre-commit install`)
- **Pas de secret en dur**, toujours via `.env`
- **Branches feature/<nom>** pour le développement, merge dans `main` après tests

## CI/CD

Trois workflows GitHub Actions configurés (avec filtres `paths:` pour ne lancer que ce qui est pertinent) :

| Workflow | Déclenchement | Vérifie |
|---|---|---|
| `backend-ci.yml` | Modifications dans `backend/**` | Lint, format, types, tests pytest avec PostgreSQL, build Docker |
| `mobile-ci.yml` | Modifications dans `mobile/**` | Format, analyze, tests, build APK debug |
| `pre-commit.yml` | Tous les push | Whitespace, YAML/JSON valides, conventional commits |
| `deploy-prod.yml` | Désactivé pour l'instant | Déploiement SSH au VPS (à activer quand l'infra sera prête) |

Après le premier push GitHub, suivre [docs/github-setup.md](docs/github-setup.md) pour configurer la branch protection sur `main`.

## Documentation pour démarrer (ordre conseillé)

1. Ce README
2. [docs/architecture.md](docs/architecture.md) — vue d'ensemble
3. [docs/adr/](docs/adr/) — du 0001 au 0006 dans l'ordre
4. [docs/data-model.md](docs/data-model.md) — entités et conventions DB
5. [docs/runbook.md](docs/runbook.md) — pour quand il faut opérer
6. [.claude/README.md](.claude/README.md) — pour configurer ton IDE/Claude Code

## Licence

À définir (probablement propriétaire pour le MVP).
