# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install       # flutter pub get
make gen           # code generation (drift, freezed, riverpod, retrofit) — run after any model/table change
make gen-watch     # code gen in watch mode during active development
make analyze       # static analysis (must pass before commit)
make format        # dart format (exits non-zero on diff — run before commit)
make test          # flutter test
make run           # run on device/emulator (dev API: http://10.0.2.2:8000)
make run-prod      # run release against prod API
make build-apk     # release APK
make clean         # clear Flutter + dart_tool caches
```

Single test: `flutter test test/auth_service_test.dart`

**Before every commit:** `make format && make analyze`

## Architecture

Feature-first Clean Architecture. Three strict layers per feature:

```
lib/features/<feature>/
├── domain/       Pure business logic — entities (freezed), repository interfaces, usecases
├── data/         Implements domain interfaces — datasources (drift local, retrofit remote), models (DTO)
└── presentation/ Flutter UI — pages, widgets, Riverpod providers
```

**Dependency rule (hard):**
- `presentation` → `domain` only, never `data`
- `data` → `domain` only
- `domain` → nothing
- Cross-feature: import other feature's `domain`, never its `data`

**Global layers:**
- `lib/core/` — `AppConfig` (dart-define constants), theme, root app widget
- `lib/database/app_database.dart` — drift schema (3 tables: `Products`, `Sales`, `SyncQueue`)
- `lib/shared/` — cross-feature widgets/utilities (currently empty)

## Features status

| Feature | Status |
|---|---|
| `auth` | Skeleton — domain entities + repository interface + auth state provider |
| `catalog`, `sales`, `printing`, `sync` | Stubs only (`.gitkeep`) |

## Key conventions

**State management:** Riverpod with `riverpod_generator`. Use `@riverpod` annotation. Providers in `<feature>/presentation/providers/`. Sealed classes for complex state (see `AuthState`).

**Local DB (drift):** Tables defined in `lib/database/app_database.dart`. Run `make gen` after any table change. Never edit `*.g.dart` files. Monetary amounts (FCFA) as `TextColumn` — preserves decimal precision.

**Networking:** dio + retrofit. Remote datasources call API via retrofit-generated client. API URL injected via `--dart-define=API_URL=...` (default: `http://10.0.2.2:8000`).

**Secure storage:** JWT (access + refresh) and hashed PIN stored in `flutter_secure_storage`. PIN never sent to backend. Max 5 PIN attempts then 5-minute lockout (constants in `AppConfig`).

**Sync strategy:** Sales are append-only via `SyncQueue` (UUID v4 generated client-side for idempotence). Catalog sync uses `dirty=true` flag. Pull on app start and connectivity restore.

**Code generation packages:** `drift_dev`, `freezed`, `json_serializable`, `riverpod_generator`, `retrofit_generator` — all triggered by `make gen`.

**Linter enforces:** single quotes, trailing commas, `const` constructors, no `dynamic`, no `print` (use `logger`), `public_member_api_docs` on all public API.

**Test convention:** files flat under `test/`, named `<feature>_<thing>_test.dart`. Mock with `mocktail`.
