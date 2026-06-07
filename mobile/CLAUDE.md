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
make run-prod      # release against prod API
make build-apk     # release APK (prod flavor)
make build-apk-dev # debug APK (dev flavor)
make clean         # clear Flutter + dart_tool caches
```

**Before every commit:** `make format && make analyze`

**Single test:** `flutter test test/auth_service_test.dart` or `flutter test test/ -k "test_pattern"`

## App entry points and flavors

Two entry points, two flavors:
- `lib/main.dart` — `AppFlavor.dev`, API `http://10.0.2.2:8000` (Android emulator localhost)
- `lib/main_prod.dart` — `AppFlavor.prod`, API prod

Both call `AppConfig.setup(flavor:, apiUrl:)` before `runApp`. `AppConfig.isDev` gates debug features. Constants (timeout, PIN lockout, etc.) live in `AppConfig` — see `core/config.dart`.

## Architecture

Feature-first Clean Architecture. Full features have 3 layers; presentation-only features (home, onboarding, settings) have only `presentation/`:

```
lib/features/<feature>/
├── domain/       Pure business logic — entities (freezed), repository interfaces
├── data/         Concrete implementations — local/remote datasources, DTOs, repositories
├── providers/    DI only — wires data → domain (imported by presentation, never data directly)
└── presentation/ Flutter UI — pages, widgets, Riverpod state providers
```

Two provider locations:
- `<feature>/providers/<feature>_di_providers.dart` — DI: repos, datasources, usecases
- `<feature>/presentation/providers/` — UI state: notifiers, AsyncValue

**Dependency rules:** `presentation` → `domain` + `providers/` (never `data` directly). `data` → `domain` only. `domain` → nothing. Cross-feature: import other feature's `domain` and `providers/`, never `data`.

**Global structure:**
- `lib/core/` — `AppConfig`, theme (Cacao & Or palette), GoRouter, Dio/Retrofit network, secure storage, sync logic
- `lib/database/` — drift schema (Products, Sales, SyncQueue tables)
- `test/` — flat test files, no directory mirroring lib/

## Features status

| Feature | Status |
|---|---|
| `auth` | Implemented — phone+password registration, phone login, PIN setup/verify, token refresh, store setup |
| `catalog` | Implemented — product listing, barcode scanning, local sync |
| `sales` | Implemented — cart, payment, receipt printing, sale history |
| `printing` | Implemented — Bluetooth thermal printer (ESC/POS via `print_bluetooth_thermal`) |
| `sync` | Implemented — offline event queue, catalog dirty-flag sync, connectivity awareness |
| `home` | Implemented — dashboard shell (presentation only) |
| `onboarding` | Implemented — tutorial (presentation only) |
| `settings` | Implemented — settings (presentation only) |

## Auth flow (ADR-0006 — phone-first)

Identifier is phone number (E.164), not email. Email is optional (account recovery only).

```
Unauthenticated → [phone+password login] → StoreSetupRequired (first reg)
                                          → PinSetupRequired (first device login)
                                          → PinRequired (PIN exists, not yet verified)
                                          → Authenticated
```

`AuthStatus` sealed class in `auth_providers.dart`. Router reads `AsyncValue<AuthStatus>` and redirects accordingly. `Routes.emailLogin` maps to `PhoneLoginPage` (name kept for backward compat).

Phone utilities: `core/utils/phone_formatter.dart` — `toE164Ci()` (local → E.164), `formatPhoneCiDisplay()` (display), `isValidLocalPhoneCi()`.

## Key conventions

**State management (Riverpod):** `@riverpod` with `riverpod_generator`. Complex state uses sealed classes (e.g., `AuthStatus`).

**Local database (drift):** Schema in `lib/database/app_database.dart`. Run `make gen` after any table/column change. Monetary amounts stored as `TextColumn`.

**Monetary amounts (FCFA):** Domain entities use `Decimal` (package `decimal`). API DTOs use `String`. Drift uses `TextColumn`. Mappers convert at boundaries — `Decimal.parse()` inbound, `.toString()` outbound. Never use `double` or `int.parse` for money.

**Networking:** Dio with auth/refresh interceptors (`core/network/`). Retrofit generates typed clients. `httpTimeoutSeconds = 60` (absorbs Render free-tier cold start ~50s).

**Secure storage:** JWT and PBKDF2-hashed PIN in `flutter_secure_storage`. PIN never sent to backend. 5 attempts → 5-minute lockout.

**Sync:** Sales append-only via `SyncQueue` (UUID v4 client-side, idempotent). Catalog: `dirty=true` flag, push full state. Pull on app start + connectivity restored.

**Theme:** "Cacao & Or" — primary brun cacao `#92400E`, secondary or `#CA8A04`. `textOnSecondary` is dark (never white on gold — fails WCAG AA). Use `AppSemanticColors` extension for dark-mode and stock-status colors.

**Code generation:** `make gen` covers `drift_dev`, `freezed`, `json_serializable`, `riverpod_generator`, `retrofit_generator`.

**Linter:** single quotes, trailing commas, `const` constructors, `prefer_final_*`, no `dynamic`/`print`, `public_member_api_docs` on all public API.

**Testing:** Flat under `test/`, named `<feature>_<concept>_test.dart`. Mock with `mocktail`.

## App initialization

`main.dart` → `AppConfig.setup()` → `initializeDateFormatting('fr_FR')` → `ProviderScope` (overrides `tokenStorageProvider` with `secureTokenStorageProvider`) → `PosMobileApp` (GoRouter + theme).

## Key files by responsibility

- `core/config.dart` — `AppConfig`, `AppFlavor`, all thresholds/constants
- `core/router/app_router.dart` — GoRouter config, `Routes` constants, auth-redirect logic
- `core/network/dio_client.dart` — Dio with auth/refresh interceptors
- `core/network/token_storage.dart` — JWT persistence interface
- `core/storage/pin_storage.dart` — PBKDF2-HMAC-SHA256 PIN hashing
- `core/sync/` — `SyncOrchestrator`, offline queue, connectivity listener
- `core/utils/phone_formatter.dart` — Ivorian phone number formatting/validation
- `features/auth/presentation/providers/auth_providers.dart` — `AuthStatus` sealed class + `Auth` notifier
- `features/sales/data/models/sale_mappers.dart` — domain `Sale` ↔ API/database (includes Decimal handling)
