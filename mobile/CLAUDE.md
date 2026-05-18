# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make install       # flutter pub get
make gen           # code generation — run after model/table/provider changes
make gen-watch     # watch mode (regenerates continuously)
make analyze       # static analysis (must pass before commit)
make format        # dart format (fails if diff — run before commit)
make test          # flutter test all
make run           # dev on emulator/device (API: http://10.0.2.2:8000)
make run-prod      # release against prod API (https://api.pos-mobile-ci.com)
make build-apk     # release APK
make clean         # clear Flutter + dart_tool caches
```

**Before every commit:** `make format && make analyze`

**Single test:** `flutter test test/auth_service_test.dart` or `flutter test test/ -k "test_pattern"`

## Architecture

Feature-first Clean Architecture. Each feature has 3 layers:

```
lib/features/<feature>/
├── domain/       Pure business logic — entities (freezed), repository interfaces
├── data/         Concrete implementations — local/remote datasources, DTOs, repositories
└── presentation/ Flutter UI — pages, widgets, Riverpod providers (state management)
```

**Dependency rules (enforced):**
- `presentation` → `domain` only (never `data`)
- `data` → `domain` only
- `domain` → nothing else (pure, independent)
- Cross-feature: import other feature's `domain`, never `data`

**Global structure:**
- `lib/core/` — app-wide: `AppConfig`, `theme`, router (GoRouter), network (Dio + Retrofit), storage, sync logic
- `lib/database/` — drift schema (Products, Sales, SyncQueue tables)
- `lib/shared/` — cross-feature UI components (currently empty)
- `test/` — flat test files, no directory mirroring lib/

## Features status

| Feature | Status |
|---|---|
| `auth` | Implemented — registration, email/PIN login, token refresh, store setup |
| `catalog` | Implemented — product listing, QR scanning (via SalesFeature), local sync |
| `sales` | Implemented — cart management, payment, receipt printing, sale history |
| `printing` | Implemented — Bluetooth thermal printer (ESC/POS via print_bluetooth_thermal) |
| `sync` | Implemented — offline event queue, catalog dirty-flag sync, connectivity awareness |

## Key conventions

**State management (Riverpod):** Use `@riverpod` annotation with `riverpod_generator`. Providers live in `<feature>/presentation/providers/`. Complex state uses sealed classes (e.g., `AuthState` for auth workflow).

**Local database (drift):** Schema in `lib/database/app_database.dart`. After any table/column change, run `make gen`. Never edit `*.g.dart` files manually. Monetary amounts stored as `TextColumn` (preserves decimal precision via `Decimal` type in domain layer).

**Monetary amounts (FCFA):** Domain entities use `Decimal` type (from `decimal` package). DTO/API models use `String`. Mappers convert: `Decimal.parse(stringValue)` on API→domain, `.toString()` on domain→storage.

**Networking:** Dio client with auth/refresh interceptors in `lib/core/network/`. Retrofit generates typed clients. API URL via `--dart-define=API_URL=...`. Token storage in `flutter_secure_storage`.

**Secure storage:** JWT (access + refresh tokens) and hashed PIN stored in `flutter_secure_storage`. PIN never sent to backend. Lockout: 5 failed attempts → 5-minute block (thresholds in `AppConfig`).

**Sync pattern:** Sales are append-only events in `SyncQueue` (client-generated UUID v4 for idempotence). Catalog: flag products `dirty=true` on local change, push full state to backend. Sync pulls on app start and when connectivity restored.

**Code generation:** `make gen` triggers `drift_dev`, `freezed`, `json_serializable`, `riverpod_generator`, `retrofit_generator`. Must run after model changes before building.

**Linter rules:** `analysis_options.yaml` enforces single quotes, trailing commas, `const` constructors, `prefer_final_*`, no `dynamic`/`print`, `public_member_api_docs` on all public API.

**Testing:** Test files flat under `test/`, named `<feature>_<concept>_test.dart` (e.g., `auth_service_test.dart`, `money_conversion_test.dart`). Mock with `mocktail`. See `test/mappers_characterization_test.dart` for integration test pattern.

## App initialization

`main.dart` sets up:
1. French date formatting (`initializeDateFormatting('fr_FR')`)
2. `ProviderScope` with token storage override
3. Root `PosMobileApp` widget (in `core/app.dart`)

Root widget uses GoRouter for navigation and `AppConfig` for theme/constants. See `core/router/app_router.dart` for route definitions.

## Key files by responsibility

- `core/network/dio_client.dart` — builds Dio with auth/refresh interceptors, error parsing
- `core/network/token_storage.dart` — interface for JWT persistence (implemented in `secure_token_storage.dart`)
- `core/sync/` — `SyncOrchestrator`, offline queue management, connectivity listener
- `core/storage/pin_storage.dart` — bcrypt PIN hashing (never stored plaintext)
- `features/auth/domain/` — `Store`, `User` entities, `AuthRepository` interface
- `features/sales/data/models/sale_mappers.dart` — converts domain `Sale` ↔ API/database models (includes Decimal handling)
