# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

POS mobile pour PME ivoiriennes (Côte d'Ivoire). Solo dev. **Monorepo:** backend FastAPI + app Flutter.

## Quick start

For detailed commands and conventions, see:
- **[Backend CLAUDE.md](./backend/CLAUDE.md)** — FastAPI, SQLAlchemy, Alembic, multi-tenancy, RLS
- **[Mobile CLAUDE.md](./mobile/CLAUDE.md)** — Flutter, Dart, Riverpod, drift, Decimal amounts

## Infra

Run from root:

```bash
docker compose up -d postgres    # démarre PostgreSQL uniquement (dev local)
docker compose up -d             # démarre tout sauf Caddy (pas de profil production)
docker compose --profile production up -d  # inclut Caddy
```

## Global rules

- **No hardcoded secrets.** Always `.env` (never committed). `APP_FRONTEND_URL` required in staging/prod (for verification/reset email links) — omitted from `.env.example`.
- **Never `git push --force` on main.**
- **Every business table has `store_id` + RLS policy.** See `docs/adr/0002-multi-tenancy-rls.md`.
- **Sales are immutable.** No UPDATE or DELETE after creation. See `docs/adr/0003-sync-hybride.md`.
- **Alembic migrations must pass `upgrade` AND `downgrade` tests** before commit. RLS policies are not auto-detected — add manually. See `.claude/rules/migrations-safety.md`.
- **Always plan mode before non-trivial tasks** (Shift+Tab × 2).

## Architecture decision records

Before any architectural change, read ADRs in `docs/adr/` (0001–0006 in order). If your decision differs, propose a new ADR that supersedes the old one.

## Context-scoped rules

`.claude/rules/` load automatically based on file edits:
- `backend-conventions.md` — Python/FastAPI/SQLAlchemy patterns
- `mobile-conventions.md` — Dart/Flutter/Riverpod patterns
- `migrations-safety.md` — mandatory migration checklist

## Documentation

- **Architecture overview:** `docs/architecture.md`
- **Data model:** `docs/data-model.md` (detailed version: `data-model-detailed.md`)
- **API:** `docs/api.md`
- **Operations runbook:** `docs/runbook.md`
- **ADRs:** `docs/adr/`