# Backoffice admin — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exposer `/api/v1/admin/*` (login admin, indicateurs, liste des boutiques, suspension) et bloquer toute boutique suspendue au prochain contact serveur.

**Architecture:** Nouveau module `app/modules/admin/` avec son propre JWT (clé `ADMIN_JWT_SECRET`, `aud="pos-admin"`) et une session `AdminDbSession` qui pose `SET LOCAL app.is_platform_admin = 'on'`. Des politiques RLS *additionnelles* n'ouvrent la lecture multi-boutiques que sous ce flag. La suspension vit dans `stores` (module stores) et est vérifiée dans `get_tenant_db`, `login` et `refresh`.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL RLS, PyJWT, pwdlib Argon2, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-10-31-backoffice-admin-design.md`

## Global Constraints

- Python 3.12+, `mypy --strict`, `async def` partout, exceptions uniquement depuis `app/core/exceptions.py`.
- Le module `admin` n'importe ni `repository.py` ni `models.py` d'un autre module : il lit `stores`/`sales`/`users` en SQL paramétré (`sqlalchemy.text` + bind params) dans `admin/repository.py`, et la suspension passe par `StoreService`.
- Montants : `String` dans les DTO (`str(Decimal)`), jamais `float`.
- Fuseau des indicateurs « du jour » : `Africa/Abidjan`.
- Token admin : `type="admin"`, `aud="pos-admin"`, durée 120 min, sans refresh.
- Verrouillage login admin : 5 échecs → `locked_until = now() + 15 min`.
- Erreur suspension : HTTP 403, `code="STORE_SUSPENDED"`, `details={"support_contact": settings.support_contact}`.
- Migration : `upgrade` ET `downgrade` testés, `down_revision = "e5b2c8d4f1a6"`.
- Avant chaque commit : `make format && make lint`. Postgres de test : `docker compose up -d postgres`.

**Écart au spec (reporté dans le spec en Task 6) :** le compte admin est créé au démarrage depuis `ADMIN_EMAIL` / `ADMIN_PASSWORD` (idempotent, pattern `app/core/seed.py`) au lieu d'une commande CLI, car Render free tier n'offre pas de shell. `seed_superadmin` existant (qui crée un *commerçant*) n'est pas touché.

## Review Focus

1. Access token émis **avant** la suspension, réutilisé sur la synchro des ventes → 403 `STORE_SUSPENDED`, aucune vente enregistrée (test Task 3).
2. Recherche contenant `%` ou `_` → traitée littéralement, pas comme joker LIKE (test Task 5).
3. Boutique sans aucune vente → `last_sale_at = null`, `sales_count = 0`, comptée « inactive » si inscrite depuis > 14 j (tests Tasks 4 et 5).
4. Login admin avec le **bon** mot de passe pendant le verrouillage → toujours 401 (test Task 2).
5. Isolation commerçant intacte après ajout des politiques admin : en rôle `pos_app` sans le flag, une boutique ne lit ni les `stores` ni les `sales` d'une autre (test Task 1).

---

### Task 1: Migration — suspension, platform_admins, politiques admin

**Files:**
- Create: `alembic/versions/f3a9b1c7d2e5_admin_backoffice.py`
- Create: `app/modules/admin/__init__.py`, `app/modules/admin/models.py`
- Modify: `app/modules/stores/models.py` (colonnes), `alembic/env.py` (import admin models), `tests/conftest.py` (`_ALL_TABLES` + `platform_admins`)
- Test: `tests/test_admin_rls.py`

**Interfaces:**
- Produces: `Store.suspended_at: Mapped[datetime | None]`, `Store.suspension_reason: Mapped[str | None]` (`String(500)`) ; `PlatformAdmin` (`platform_admins` : `id` UUID PK, `email` `String(255)` unique en minuscules, `password_hash` `String(255)`, `failed_login_count` int défaut 0, `locked_until` timestamptz null, `last_login_at` timestamptz null, `created_at`, `updated_at` + trigger `set_updated_at`). Politiques : `rls_stores_platform_admin_read` (FOR SELECT), `rls_stores_platform_admin_update` (FOR UPDATE, USING + WITH CHECK), `rls_sales_platform_admin_read` (FOR SELECT), toutes conditionnées par `current_setting('app.is_platform_admin', true) = 'on'`. `users` n'a pas de RLS : rien à ajouter.

- [ ] **Step 1: Write the failing tests** in `tests/test_admin_rls.py` (helpers `_create_user_with_store` repris de `tests/test_rls_isolation.py`) :
  - `test_admin_flag_sees_all_stores` : 2 boutiques ; `SET LOCAL ROLE pos_app` + `SET LOCAL app.is_platform_admin = 'on'` → `SELECT count(*) FROM stores` == 2.
  - `test_tenant_without_flag_still_isolated` : `SET LOCAL ROLE pos_app` + `app.current_store_id = A` → `SELECT id FROM stores` == [A] et `SELECT count(*) FROM sales WHERE store_id = B` == 0 (B a une vente).
  - `test_admin_flag_can_update_suspension` : sous flag, `UPDATE stores SET suspended_at = now() WHERE id = B` → rowcount 1.
- [ ] **Step 2:** `uv run pytest tests/test_admin_rls.py -v` → FAIL (colonne `suspended_at` absente).
- [ ] **Step 3:** Écrire la migration (colonnes `stores`, table `platform_admins` + `chk_platform_admins_email_lowercase` + trigger `updated_at`, 3 politiques) et son `downgrade` exactement inverse ; ajouter les colonnes à `Store`, créer `PlatformAdmin`, importer dans `alembic/env.py`, ajouter `platform_admins` à `_ALL_TABLES`. Docstring : « schéma uniquement, aucune donnée modifiée ».
- [ ] **Step 4:** `uv run pytest tests/test_admin_rls.py tests/test_rls_isolation.py -v` → PASS ; puis `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` sur la DB de dev → sans erreur.
- [ ] **Step 5:** `make format && make lint && git commit -m "feat(admin): migration suspension, platform_admins et politiques RLS admin"`

### Task 2: Auth admin — config, token, seed, login avec verrouillage

**Files:**
- Modify: `app/core/config.py`, `app/core/security.py`, `app/core/seed.py`, `app/main.py`
- Create: `app/modules/admin/{schemas,repository,service,router,dependencies}.py`
- Test: `tests/test_admin_auth.py`

**Interfaces:**
- Produces (config) : `admin_jwt_secret_key: SecretStr = SecretStr("")`, `admin_token_expire_minutes: int = 120`, `admin_email: str = ""`, `admin_password: SecretStr = SecretStr("")`, `support_contact: str = ""`.
- Produces (security) : `create_admin_token(admin_id: UUID) -> str` ; `decode_admin_token(token: str) -> dict[str, Any] | None` (vérifie `aud="pos-admin"` et `type="admin"` ; `None` si clé vide, token invalide ou expiré).
- Produces (admin) : `AdminLoginRequest(email: EmailStr, password: str)`, `AdminTokenResponse(access_token: str, token_type: Literal["bearer"], expires_in: int)` ; `AdminService.login(payload) -> AdminTokenResponse` ; `AdminService.ensure_seed_admin(email: str, password: str) -> None` ; `get_current_admin_id(request: Request, db: DbSession) -> UUID` et alias `CurrentAdminId` dans `admin/dependencies.py` ; route `POST /api/v1/admin/auth/login` (200).
- Produces (seed) : `seed_platform_admin()` dans `app/core/seed.py`, appelé dans le lifespan de `app/main.py` à côté de `seed_superadmin()` ; ne fait rien si `ADMIN_EMAIL`/`ADMIN_PASSWORD` vides ; ne réécrit jamais un admin existant.

- [ ] **Step 1: Write the failing tests** (`tests/test_admin_auth.py` ; admin créé via `AdminService(db_session).ensure_seed_admin("admin@test.ci", "S3cret-pass!")` ; `settings.admin_jwt_secret_key` patché à une valeur de 48 caractères) :
  - `test_admin_login_success` → 200, `token_type == "bearer"`, `expires_in == 7200`, `decode_admin_token(token)["sub"] == str(admin.id)`.
  - `test_admin_login_wrong_password` → 401, `code == "UNAUTHORIZED"`.
  - `test_admin_login_unknown_email` → 401 avec le **même** `detail` que le mauvais mot de passe.
  - `test_admin_locked_after_5_failures` : 5 échecs puis bon mot de passe → 401 ; `locked_until` > now.
  - `test_admin_unlocked_after_15_minutes` : `locked_until` forcé dans le passé → 200 et `failed_login_count == 0`.
  - `test_merchant_token_rejected_on_admin_route` : `create_access_token(user.id, store.id)` sur `GET /api/v1/admin/metrics` → 401.
  - `test_admin_token_rejected_on_merchant_route` : token admin sur `GET /api/v1/stores/me` → 401.
  - `test_admin_login_disabled_without_secret` : `admin_jwt_secret_key = ""` → 403, `detail == "Admin access is not configured."`.
  - `test_seed_admin_idempotent` : deux appels → une seule ligne, hash inchangé.
- [ ] **Step 2:** `uv run pytest tests/test_admin_auth.py -v` → FAIL (imports manquants).
- [ ] **Step 3:** Implémenter. Login : email `.strip().lower()` ; email inconnu → `verify_password` contre un hash factice (temps constant) ; message unique `"Invalid email or password."` ; succès → compteur remis à 0, `last_login_at = now()`. Router enregistré avec `prefix=f"{api_v1_prefix}/admin"`, `tags=["admin"]`. `get_current_admin_id` lit `Authorization: Bearer`, appelle `decode_admin_token`, vérifie que l'admin existe, sinon `UnauthorizedError("Admin authentication required")`. Ne jamais logger mot de passe ni token. `GET /admin/metrics` déclaré ici avec `CurrentAdminId` (corps complété en Task 4).
- [ ] **Step 4:** `uv run pytest tests/test_admin_auth.py -v` → PASS.
- [ ] **Step 5:** `make format && make lint && git commit -m "feat(admin): authentification administrateur plateforme"`

### Task 3: Blocage des boutiques suspendues

**Files:**
- Modify: `app/core/exceptions.py`, `app/core/db.py`, `app/modules/auth/service.py` (login + refresh), `tests/conftest.py` (override `get_tenant_db`)
- Test: `tests/test_store_suspension.py`

**Interfaces:**
- Produces : `AppError.__init__(message, field=None, details: dict[str, str] | None = None)` ; le handler n'ajoute la clé `"details"` que si elle n'est pas `None` (format inchangé pour les autres erreurs). `StoreSuspendedError(ForbiddenError)`, `code = "STORE_SUSPENDED"`, construit sans argument : message `"Store is suspended."`, `details={"support_contact": settings.support_contact}`. `assert_store_active(db: AsyncSession, store_id: UUID) -> None` dans `app/core/db.py` (SQL `SELECT suspended_at FROM stores WHERE id = :sid`, lève `StoreSuspendedError`), appelée par `get_tenant_db` après le `SET LOCAL` **et** par l'override de `tests/conftest.py` (sinon les tests contournent le contrôle).

- [ ] **Step 1: Write the failing tests** (`suspended_at` posé en SQL dans la fixture ; `settings.support_contact` patché à `"+2250700000000"`) :
  - `test_suspended_store_blocked_on_get_me` → `GET /api/v1/stores/me` 403, `code == "STORE_SUSPENDED"`, `details["support_contact"] == "+2250700000000"`.
  - `test_token_issued_before_suspension_blocked_on_sync` : token créé, puis suspension, puis POST de synchro des ventes (payload `_sale_payload` de `tests/test_sync.py`) → 403 et `count(*) FROM sales == 0`.
  - `test_suspended_store_login_refused` → `POST /api/v1/auth/login` 403 `STORE_SUSPENDED`.
  - `test_suspended_store_refresh_refused` → `POST /api/v1/auth/refresh` 403 `STORE_SUSPENDED`.
  - `test_reactivated_store_works_again` : `suspended_at = NULL` → `GET /stores/me` 200.
  - `test_other_errors_have_no_details_key` : une 404 → `"details" not in body`.
- [ ] **Step 2:** `uv run pytest tests/test_store_suspension.py -v` → FAIL.
- [ ] **Step 3:** Implémenter ; dans `login`/`refresh`, après récupération de la boutique : `if store.suspended_at is not None: raise StoreSuspendedError()`.
- [ ] **Step 4:** `uv run pytest -v` (suite complète) → PASS.
- [ ] **Step 5:** `make format && make lint && git commit -m "feat(stores): blocage des boutiques suspendues au prochain contact serveur"`

### Task 4: Indicateurs plateforme

**Files:**
- Modify: `app/modules/admin/{dependencies,repository,service,schemas,router}.py`
- Test: `tests/test_admin_metrics.py`

**Interfaces:**
- Produces : `get_admin_db(db: DbSession, _admin: CurrentAdminId) -> AsyncSession` (pose `SET LOCAL app.is_platform_admin = 'on'`) et alias `AdminDbSession`. `PlatformMetrics(stores_total: int, stores_new_7d: int, stores_active_7d: int, stores_inactive_14d: int, stores_suspended: int, sales_today_count: int, sales_today_amount: str, sales_7d_count: int, sales_7d_amount: str)`. `GET /api/v1/admin/metrics` → 200 `PlatformMetrics`.
- Définitions (spec 4.1) : actives = non suspendues avec ≥ 1 vente `created_at >= now() - interval '7 days'` ; inactives = non suspendues, `stores.created_at < now() - interval '14 days'` et aucune vente `>= now() - interval '14 days'` ; « aujourd'hui » = `created_at >= (date_trunc('day', now() AT TIME ZONE 'Africa/Abidjan') AT TIME ZONE 'Africa/Abidjan')` ; montants = `COALESCE(SUM(total_amount), 0)` convertis en `str`. Ventes des boutiques suspendues incluses dans les volumes. Agrégation en SQL.
- Test fixture `admin_client` (dans `tests/conftest.py`) : surcharge `get_admin_db` pour ajouter `SET LOCAL ROLE pos_app` + le flag, afin que le RLS soit réellement appliqué, et fournit un header admin valide.

- [ ] **Step 1: Write the failing tests** — `test_metrics_on_known_dataset` : A (créée il y a 30 j, 2 ventes aujourd'hui `"1500.00"` et `"2500.00"`), B (créée il y a 30 j, 1 vente il y a 20 j), C (créée hier, 0 vente), D (créée il y a 30 j, suspendue, 1 vente aujourd'hui `"1000.00"`) → `stores_total == 4`, `stores_new_7d == 1`, `stores_active_7d == 1`, `stores_inactive_14d == 1`, `stores_suspended == 1`, `sales_today_count == 3`, `Decimal(sales_today_amount) == Decimal("5000.00")`, `sales_7d_count == 3`, `Decimal(sales_7d_amount) == Decimal("5000.00")`. Et `test_metrics_requires_admin` → 401 sans token.
- [ ] **Step 2:** `uv run pytest tests/test_admin_metrics.py -v` → FAIL.
- [ ] **Step 3:** Implémenter repository (SQL) → service → router.
- [ ] **Step 4:** `uv run pytest tests/test_admin_metrics.py -v` → PASS.
- [ ] **Step 5:** `make format && make lint && git commit -m "feat(admin): indicateurs plateforme"`

### Task 5: Liste des boutiques, suspension et réactivation

**Files:**
- Modify: `app/modules/admin/{repository,service,schemas,router}.py`, `app/modules/stores/{service,repository}.py`
- Test: `tests/test_admin_stores.py`

**Interfaces:**
- Produces (stores) : `StoreService.set_suspension(store_id: UUID, suspended: bool, reason: str | None) -> None` — suspendre une boutique déjà suspendue conserve `suspended_at` et met à jour la raison ; réactiver remet les deux à `NULL` ; `NotFoundError` si absente ; ne modifie aucune autre colonne.
- Produces (admin) : `AdminStoreItem(id: UUID, name: str, owner_phone: str, created_at: datetime, last_sale_at: datetime | None, sales_count: int, suspended_at: datetime | None, suspension_reason: str | None)` ; `AdminStorePage(items: list[AdminStoreItem], total: int)` ; `SuspendRequest(reason: str | None = Field(default=None, max_length=500))`.
- Routes :
  - `GET /api/v1/admin/stores?search=&status=all|active|suspended&inactive=false&sort=last_sale|created&limit=20&offset=0` (`limit` 1–100, `offset` ≥ 0) → `AdminStorePage`. `search` matche `stores.name` ou `users.phone_number` en `ILIKE ... ESCAPE '\'` avec `%`, `_`, `\` échappés. `inactive=true` applique la définition de Task 4. `sort=last_sale` : `last_sale_at DESC NULLS LAST, created_at DESC` ; `sort=created` : `created_at DESC`.
  - `POST /api/v1/admin/stores/{store_id}/suspend` (body `SuspendRequest`) → 200 `AdminStoreItem`.
  - `POST /api/v1/admin/stores/{store_id}/reactivate` → 200 `AdminStoreItem`.

- [ ] **Step 1: Write the failing tests** :
  - `test_list_stores_fields` : boutique avec 3 ventes → `sales_count == 3`, `last_sale_at` == date de la plus récente, `owner_phone == user.phone_number`.
  - `test_list_store_without_sales` : `last_sale_at is None`, `sales_count == 0`.
  - `test_list_filters_status_and_inactive` : jeu de Task 4 ; `status=suspended` → [D] ; `inactive=true` → [B].
  - `test_list_search_escapes_wildcards` : `"Chez 100%"` et `"Chez 1000"` ; `search=100%` → seulement la première.
  - `test_list_pagination` : 25 boutiques, `limit=20&offset=20` → 5 items, `total == 25`.
  - `test_suspend_then_merchant_blocked` : suspend `reason="Impayé"` → 200, `suspension_reason == "Impayé"` ; puis token commerçant sur `GET /stores/me` → 403 `STORE_SUSPENDED`.
  - `test_suspend_twice_keeps_first_date`.
  - `test_reactivate` : `suspended_at is None`, commerçant de nouveau 200.
  - `test_suspend_unknown_store` → 404.
  - `test_suspend_reason_too_long` (501 caractères) → 422.
- [ ] **Step 2:** `uv run pytest tests/test_admin_stores.py -v` → FAIL.
- [ ] **Step 3:** Implémenter (le router passe `AdminDbSession` à `StoreService(db)` pour la suspension, puis relit l'item via le repository admin).
- [ ] **Step 4:** `uv run pytest -v` → PASS ; `make type-check` → 0 erreur ; `uv run pytest --cov=app/modules/admin --cov-report=term` → ≥ 70 %.
- [ ] **Step 5:** `make format && make lint && git commit -m "feat(admin): liste des boutiques, suspension et réactivation"`

### Task 6: ADR-0012 et documentation

**Files:**
- Create: `docs/adr/0012-acces-administrateur-plateforme.md` (depuis `docs/adr/_template.md`)
- Modify: `docs/adr/README.md`, `docs/api.md` (section Admin + code `STORE_SUSPENDED` + clé `details`), `docs/architecture.md:376`, `docs/superpowers/specs/2026-10-31-backoffice-admin-design.md` (écart seed par env), `CLAUDE.md` (ligne `modules/admin/` dans « Key files by responsibility »)

- [ ] **Step 1:** Rédiger l'ADR : contexte (ADR-0002), décision (flag de session + politiques additionnelles, clé JWT distincte, admin seedé par env), alternatives rejetées (rôle `BYPASSRLS` : contourne toutes les tables sans granularité ; fonctions `SECURITY DEFINER` : logique dispersée en SQL), conséquences, et le point ouvert « rôle DB réellement utilisé en dev/prod ».
- [ ] **Step 2:** Mettre à jour les autres fichiers listés.
- [ ] **Step 3:** `git commit -m "docs(admin): ADR-0012 accès administrateur plateforme"`

### Task 7: Configuration Render (avec l'utilisateur)

- [ ] **Step 1:** Donner à l'utilisateur la liste des variables Render : `ADMIN_JWT_SECRET` (générée localement par `python -c "import secrets; print(secrets.token_urlsafe(48))"` et saisie par lui), `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SUPPORT_CONTACT`, et `CORS_ORIGINS` complété avec l'URL Netlify (connue au plan front, Task 5).
- [ ] **Step 2:** Après déploiement : `curl -s -o /dev/null -w "%{http_code}\n" -X POST https://pos-mobile-vkuh.onrender.com/api/v1/admin/auth/login -H 'Content-Type: application/json' -d '{"email":"x@x.ci","password":"bad"}'` → `401`.
