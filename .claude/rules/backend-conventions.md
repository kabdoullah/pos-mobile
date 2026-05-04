---
description: Conventions et patterns spécifiques au backend FastAPI
globs:
  - "backend/**/*.py"
  - "backend/pyproject.toml"
  - "backend/Dockerfile"
---

# Conventions backend (FastAPI / Python)

## Structure des modules

Chaque module dans `backend/app/modules/` suit la même structure :

```
modules/<feature>/
├── router.py        Routes FastAPI uniquement (couche HTTP)
├── service.py       Logique métier
├── repository.py    Accès données SQLAlchemy
├── schemas.py       Modèles Pydantic (DTO request/response)
├── models.py        Modèles SQLAlchemy (entités DB)
└── exceptions.py    Exceptions métier spécifiques (optionnel)
```

**Règle critique de découplage** : un module peut importer le `service.py` et `schemas.py` d'un autre module, mais JAMAIS son `repository.py` ou ses `models.py`.

## Conventions Python

- Python 3.12+ uniquement, utiliser les nouveautés (`type | None` au lieu de `Optional[Type]`, `dict[str, X]` au lieu de `Dict`)
- Type hints partout (mypy strict est activé, voir `backend/pyproject.toml`)
- Utiliser `Annotated[X, Depends(...)]` pour les dépendances FastAPI
- Type aliases dans `core/db.py` (`DbSession`, `TenantDbSession`) et `core/dependencies.py` (`CurrentUserId`, `CurrentStoreId`) pour réduire le boilerplate
- Async partout : tous les endpoints, services, repositories sont `async def`

## Routes FastAPI

- Préfixe `/api/v1/<module>` pour toutes les routes métier
- Toujours déclarer `response_model` et `status_code` explicitement
- Utiliser les exceptions de `core/exceptions.py` (`NotFoundError`, `ConflictError`, etc.) — JAMAIS lever des `HTTPException` manuelles

## Modèles SQLAlchemy

- Hériter de `Base` défini dans `app/core/db.py`
- UUID v4 comme PK : `mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)`
- Toutes les tables métier ont `store_id`, `created_at`, `updated_at`
- Les ventes sont **immuables** : pas d'UPDATE après création
- Soft delete via `deleted_at TIMESTAMPTZ NULL` pour les produits
- Voir `docs/data-model.md` pour les conventions complètes

## Migrations Alembic

- Une migration par feature, jamais une migration "init" géante
- **Toujours tester `upgrade` ET `downgrade`** localement avant de commit
- Les politiques RLS PostgreSQL doivent être ajoutées manuellement (Alembic ne les autodetecte pas)
- Importer chaque nouveau module avec modèles dans `alembic/env.py`

## Multi-tenancy + RLS

- Voir `docs/adr/0002-multi-tenancy-rls.md`
- Toute nouvelle table métier doit :
  1. Avoir une colonne `store_id UUID NOT NULL`
  2. Avoir un index sur `store_id`
  3. Avoir une politique RLS dans la même migration
  4. Avoir un test d'isolation (user A ne peut pas lire les données de user B)

## Sécurité

- Jamais de `SELECT *` avec construction de string : toujours SQLAlchemy ou paramètres bindés
- Jamais de secret en dur : tout via `app.core.config.settings`
- Le password est hashé via `app.core.security.hash_password` (bcrypt cost 12)
- Pas de logs avec des données sensibles (password, JWT, PIN)

## Tests

- Pytest + pytest-asyncio (mode auto activé)
- Fixtures dans `tests/conftest.py`
- Tests d'isolation RLS obligatoires pour toute nouvelle table tenant
- Couverture cible 70% sur les modules métier
