# POS Mobile Backend

FastAPI + PostgreSQL backend for **Ma Caisse**, a point of sale app for Ivorian SMEs (mobile app: repo `pos-mobile-app`). Deployed on Render: `https://pos-mobile-vkuh.onrender.com`.

## Quick start

```bash
docker compose up -d postgres   # local PostgreSQL on 127.0.0.1:5432
make install                    # uv sync (dev dependencies included)
make migrate                    # alembic upgrade head
make dev                        # server with hot reload
make seed                       # optional: test user, store and products
```

Settings are read from the environment or a `.env` file (not versioned). Required: `DATABASE_URL` (asyncpg, e.g. `postgresql+asyncpg://pos:pos_local@localhost:5432/pos`) and `JWT_SECRET_KEY`. Optional: `RESEND_API_KEY`, `CORS_ORIGINS`, `REDIS_URL`, `SUPERADMIN_*` — see `app/core/config.py`.

## Modules

Each module in `app/modules/` has `router.py`, `service.py`, `repository.py`, `schemas.py`, `models.py`. A module may import another module's service and schemas, never its repository or models.

| Module | Scope |
|---|---|
| `auth` | Phone-first registration and login, JWT access/refresh, password reset, profile, account deletion (`DELETE /api/v1/users/me`, ADR-0011) |
| `stores` | Store settings and logo |
| `catalog` | Products, categories, product images, bulk import |
| `sales` | Immutable sales, receipts |
| `inventory` | Stock movements (immutable) |
| `returns` | Customer returns and refunds (ADR-0010) |
| `sync` | Offline push (sales, returns, catalog) and pull (`GET /api/v1/sync/changes`) |

Multi-tenancy is enforced by PostgreSQL Row-Level Security on `app.current_store_id` (ADR-0002). Sales, returns and stock movements are immutable by trigger; the only exception is the full purge of a store when its owner deletes the account (ADR-0011).

## Commands

```bash
make help                          # list commands
make format / make lint            # ruff
make type-check                    # mypy (strict)
make test                          # pytest (needs Postgres on localhost:5432)
make test-cov                      # coverage report in htmlcov/
make makemigration MSG="..."       # new Alembic migration
make migration-history
```

Tests recreate a `pos_test` database, apply every migration and use a non-superuser `pos_app` role so RLS policies are actually enforced. Single test: `uv run pytest tests/test_account_deletion.py -k purge`.

Migrations: RLS policies and triggers are not autodetected — write them by hand, test `upgrade` and `downgrade`, and back up production before applying (`docs/runbook.md`).

## Docs

- Guidelines: `CLAUDE.md`
- API: `docs/api.md` · data model: `docs/data-model.md` · runbook: `docs/runbook.md`
- Architecture decisions: `docs/adr/`
- Public pages (GitHub Pages, served from `docs/`): [privacy policy](https://kabdoullah.github.io/pos-mobile/privacy-policy), [account deletion](https://kabdoullah.github.io/pos-mobile/account-deletion)
