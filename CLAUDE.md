# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

POS mobile pour PME ivoiriennes. Solo dev. Architecture : backend FastAPI (`backend/`) + app Flutter (`mobile/`).

## Commands

### Backend (`cd backend`)

```bash
make install         # uv sync
make dev             # uvicorn --reload sur :8000
make format          # ruff format + ruff check --fix
make lint            # ruff check (sans modifier)
make type-check      # mypy strict
make test            # pytest — nécessite Docker (pos-mobile-postgres-1) en cours d'exécution
make test-cov        # pytest + rapport HTML dans htmlcov/
make migrate         # alembic upgrade head
make makemigration MSG="desc"  # génère une migration
make seed            # insère user/boutique/produits de test
```

Single test : `uv run pytest tests/modules/auth/test_auth_service.py -k "test_login"`

**Prérequis tests :** `docker compose up -d postgres` — `conftest.py` recrée `pos_test` via `docker exec pos-mobile-postgres-1 psql` et crée le rôle `pos_app` (non-superuser) pour que les politiques RLS soient effectivement appliquées.

**Before every commit:** `make format && make lint`

### Mobile (`cd mobile`)

```bash
make install         # flutter pub get
make gen             # build_runner build — lancer après tout changement de modèle/table
make gen-watch       # build_runner watch pendant le dev actif
make analyze         # flutter analyze (obligatoire avant commit)
make format          # dart format (exit non-zero si diff)
make test            # flutter test
make run             # émulateur Android, API sur http://10.0.2.2:8000 (--dart-define=API_URL=...)
make run-prod        # release contre l'API de prod
make build-apk       # APK release
make clean           # vide les caches Flutter + dart_tool
```

Single test : `flutter test test/auth_service_test.dart`

**Before every commit:** `make format && make analyze`

### Infra (racine)

```bash
docker compose up -d postgres    # démarre PostgreSQL uniquement (dev local)
docker compose up -d             # démarre tout sauf Caddy (pas de profil production)
docker compose --profile production up -d  # inclut Caddy
```

## Backend architecture

### Flux JWT → RLS (non-obvious, span 3 fichiers)

Chaque requête authentifiée passe par cette chaîne :

1. `StoreContextMiddleware` (`core/middleware.py`) : décode le JWT, stocke `user_id` et `store_id` dans `request.state`
2. `get_tenant_db()` (`core/db.py`) : exécute `SET LOCAL app.current_store_id = :sid` sur la session PostgreSQL
3. RLS PostgreSQL filtre automatiquement les lignes — toutes les queries n'ont accès qu'aux données de la boutique

Conséquence : utiliser `TenantDbSession` (pas `DbSession`) pour toutes les routes authentifiées.

### Type aliases à utiliser dans les routes

Définis dans `core/db.py` et `core/dependencies.py` — réduisent le boilerplate :

```python
# core/db.py
DbSession = Annotated[AsyncSession, Depends(get_db)]          # routes publiques
TenantDbSession = Annotated[AsyncSession, Depends(get_tenant_db)]  # routes auth (injecte RLS)

# core/dependencies.py
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
CurrentStoreId = Annotated[UUID, Depends(get_current_store_id)]
```

Signature type d'un endpoint protégé :

```python
async def my_endpoint(db: TenantDbSession, user_id: CurrentUserId) -> ...:
```

### Exceptions

Lever uniquement les exceptions de `core/exceptions.py` : `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`, `ValidationError`. Jamais `HTTPException` directement — le handler centralisé formate la réponse JSON.

### Modules métier

`backend/app/modules/` : `auth`, `stores`, `catalog`, `sales`, `sync`. Chaque module : `router.py` → `service.py` → `repository.py` + `models.py` + `schemas.py`.

Préfixes routes (attention : `catalog` monte sur `/api/v1/products`, pas `/api/v1/catalog`).

Templates email : `backend/app/templates/emails/` (HTML + TXT pour vérification et reset mot de passe).

Règle d'import croisé : un module peut importer `service.py` et `schemas.py` d'un autre, **jamais** son `repository.py` ou `models.py`.

## Mobile architecture

### Features status

| Feature | État |
|---|---|
| `auth` | Skeleton — domain entities + repository interface + AuthState provider |
| `catalog`, `sales`, `printing`, `sync` | Stubs uniquement (`.gitkeep`) |

### Couches par feature (règle stricte)

```
lib/features/<feature>/
├── domain/       Entités pures (freezed), interfaces repository, use cases — n'importe rien d'autre
├── data/         Implémente domain — datasources (drift local, retrofit remote)
└── presentation/ Pages, widgets, Riverpod providers
```

`presentation` → `domain` uniquement. `data` → `domain` uniquement. Cross-feature : importer uniquement le `domain` de l'autre feature.

### Base de données locale (drift)

Schéma dans `lib/database/app_database.dart` (3 tables : `Products`, `Sales`, `SyncQueue`). Après tout changement : `make gen`. Les montants FCFA sont en `TextColumn` (précision décimale).

## Règles globales

- **Jamais de secret en dur.** Utiliser `.env` (non committé). `APP_FRONTEND_URL` requis en staging/prod (base URL des liens dans les emails de vérification/reset) — absent du `.env.example`.
- **Jamais `git push --force` sur main.**
- **Toute table métier a `store_id` + politique RLS.** Voir `docs/adr/0002-multi-tenancy-rls.md`.
- **Les ventes sont immuables.** Pas d'UPDATE ni de DELETE après création. Voir `docs/adr/0003-sync-hybride.md`.
- **Les migrations Alembic doivent être testées en `upgrade` ET `downgrade`** avant commit. Les politiques RLS ne sont pas auto-détectées : les ajouter manuellement. Voir `.claude/rules/migrations-safety.md`.
- **Toujours plan mode (Shift+Tab × 2) avant toute tâche non triviale.**

## ADRs

Avant tout changement architectural, lire les ADRs dans `docs/adr/` (0001 à 0005). Si la décision diffère d'un ADR, proposer un nouvel ADR qui supersede l'ancien.

## Règles contextuelles

`.claude/rules/` se chargent automatiquement selon les fichiers édités :
- `backend-conventions.md` — conventions Python/FastAPI/SQLAlchemy
- `mobile-conventions.md` — conventions Dart/Flutter/Riverpod
- `migrations-safety.md` — checklist et patterns obligatoires pour les migrations