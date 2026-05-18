# Backend POS Mobile

API FastAPI multi-tenant pour l'application POS Mobile.

## Stack

- **Python 3.12+** géré par `uv`
- **FastAPI** + Uvicorn
- **PostgreSQL 17** + SQLAlchemy 2.0 async + Alembic
- **Ruff** comme formatter et linter (PEP8 + plus)
- **Pytest** + httpx pour les tests
- **mypy** en mode strict pour le type checking

## Démarrage rapide

```bash
# Installer uv si tu ne l'as pas
curl -LsSf https://astral.sh/uv/install.sh | sh

# Installer les dépendances
make install

# Copier les variables d'environnement
cp .env.example .env
# Éditer .env (notamment générer un JWT_SECRET_KEY)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Lancer la DB via Docker
docker compose up -d postgres

# Appliquer les migrations
make migrate

# Lancer le serveur en dev
make dev
```

L'API est sur http://localhost:8000. La doc Swagger : http://localhost:8000/docs.

## Structure

```
backend/
├── app/
│   ├── main.py              Point d'entrée FastAPI
│   ├── core/                Code transverse (config, DB, security, middleware)
│   └── modules/             Modules métier (auth, stores, catalog, sales, sync)
│       └── <module>/
│           ├── router.py    Routes FastAPI
│           ├── service.py   Logique métier
│           ├── repository.py  Accès données SQLAlchemy
│           ├── schemas.py   Modèles Pydantic (DTO)
│           └── models.py    Modèles SQLAlchemy (entités DB)
├── alembic/                 Migrations DB
├── tests/                   Tests pytest
├── pyproject.toml           Config uv + ruff + pytest + mypy
├── Dockerfile               Image production
└── Makefile                 Commandes courantes
```
feat(mobile): add sync orchestration, triggers and user-facing sync indicators
## Conventions

Voir `docs/architecture.md` à la racine du repo pour les conventions de découpage en modules. En résumé :

- **Un module = une feature métier** (auth, catalog, sales, etc.)
- **Communication entre modules via les services**, jamais via les repositories ou modèles directement
- **Chaque table métier a un `store_id`** + Row-Level Security PostgreSQL activé
- **Pas de SQL raw** sauf cas exceptionnel et documenté

## Commandes utiles

```bash
make help           # liste toutes les commandes
make format         # formate avec ruff
make lint           # vérifie sans modifier
make type-check     # mypy
make test           # tests
make test-cov       # tests + couverture HTML
make migrate        # applique les migrations
make makemigration MSG="add products table"  # crée une migration
```

## Variables d'environnement

Voir `.env.example` pour la liste complète. Les secrets ne sont jamais committés.

## Documentation

- Architecture globale : `../docs/architecture.md`
- Modèle de données : `../docs/data-model.md`
- ADRs : `../docs/adr/`
- Runbook ops : `../docs/runbook.md`
