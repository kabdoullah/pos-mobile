# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

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
make shell           # Python shell avec contexte de l'app
```

**Single test:** `uv run pytest tests/modules/auth/test_auth_service.py -k "test_login"`

**Test prerequisites:** `docker compose up -d postgres` — `conftest.py` recreates `pos_test` DB and creates `pos_app` role (non-superuser) so RLS policies are actually enforced.

**Before every commit:** `make format && make lint`

## Architecture

### Module structure

Each module in `app/modules/` follows strict layering:

```
modules/<feature>/
├── router.py        FastAPI routes only (HTTP layer)
├── service.py       Business logic
├── repository.py    SQLAlchemy data access
├── schemas.py       Pydantic models (request/response DTOs)
├── models.py        SQLAlchemy entities (DB models)
└── exceptions.py    Feature-specific exceptions (optional)
```

**Critical decoupling rule:** A module can import another module's `service.py` and `schemas.py`, but NEVER its `repository.py` or `models.py`.

### Multi-tenancy + RLS flow (non-obvious, spans 3 files)

Every authenticated request flows through:

1. `StoreContextMiddleware` (`core/middleware.py`) — decodes JWT, stores `user_id` and `store_id` in `request.state`
2. `get_tenant_db()` (`core/db.py`) — executes `SET LOCAL app.current_store_id = :sid` on PostgreSQL session
3. RLS PostgreSQL — automatically filters rows; all queries only see the store's data

**Consequence:** Use `TenantDbSession` (not `DbSession`) for all authenticated routes.

### Type aliases for routes

Defined in `core/db.py` and `core/dependencies.py` to reduce boilerplate:

```python
# core/db.py
DbSession = Annotated[AsyncSession, Depends(get_db)]          # public routes
TenantDbSession = Annotated[AsyncSession, Depends(get_tenant_db)]  # auth routes (injects RLS)

# core/dependencies.py
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
CurrentStoreId = Annotated[UUID, Depends(get_current_store_id)]
```

Typical protected endpoint signature:

```python
async def my_endpoint(db: TenantDbSession, user_id: CurrentUserId) -> ...:
```

### Exception handling

Only raise exceptions from `core/exceptions.py`: `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`, `ValidationError`. Never raise `HTTPException` directly — the centralized handler formats JSON responses.

### Key files by responsibility

- `core/db.py` — SQLAlchemy setup, DB session factories, type aliases
- `core/middleware.py` — JWT decoding, store context injection, RLS setup
- `core/security.py` — password hashing (Argon2), JWT generation/verification
- `core/config.py` — environment variables and app config (via Pydantic)
- `core/exceptions.py` — all exception types + centralized error handler
- `modules/auth/` — registration, login, token refresh, PIN login, store setup
- `modules/stores/` — store profile, settings
- `modules/catalog/` — products (with soft delete via `deleted_at`)
- `modules/sales/` — append-only sales, immutable after creation
- `modules/sync/` — sync queue, dirty-flag catalog syncs

## Key conventions

**Python 3.12+** with type hints. `mypy --strict` enabled. Use Python 3.12+ syntax (`type | None` not `Optional`, `dict[str, X]` not `Dict`).

**Async everywhere:** All endpoints, services, repositories are `async def`.

**Database models:**
- UUID v4 as PK: `mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)`
- Every business table has `store_id`, `created_at`, `updated_at`
- Sales are **immutable** — no UPDATE after creation (enforce via trigger)
- Soft delete: `deleted_at TIMESTAMPTZ NULL` for products

**Migrations (Alembic):**
- One migration per feature, never a giant "init"
- **Always test `upgrade` AND `downgrade`** locally before commit
- RLS policies are NOT auto-detected by Alembic — add them manually in migrations
- Import every new module's models in `alembic/env.py`

**Monetary amounts (FCFA):**
- API/DTO: `String`
- Database: `String` (via Decimal → `.toString()`)
- Domain: `decimal.Decimal` (exact arithmetic)
- Conversion: `Decimal.parse(stringValue)` on API→domain, `.toString()` on domain→storage

**Testing:**
- Pytest + pytest-asyncio (auto mode enabled)
- Fixtures in `tests/conftest.py`
- RLS isolation tests required for all new tenant tables (user A cannot read user B's data)
- Coverage target: 70% on business modules

## Security

- No hardcoded secrets — everything via `.env` (not committed)
- No `SELECT *` via string construction — always SQLAlchemy or parameterized queries
- Password: Argon2 via `app.core.security.hash_password` (`pwdlib.PasswordHash.recommended()`)
- No sensitive data in logs (password, JWT, PIN)
- JWT stored in `httpx.Client` cookies for Swagger auth; also returned in responses for mobile

## See also

- Architecture details: `../docs/architecture.md`
- Data model: `../docs/data-model.md`
- ADRs: `../docs/adr/`
- Conventions (path-scoped): `../.claude/rules/backend-conventions.md`
- Migration safety: `../.claude/rules/migrations-safety.md`
