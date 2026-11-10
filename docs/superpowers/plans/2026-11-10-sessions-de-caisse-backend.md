# Sessions de caisse — backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter au backend FastAPI les sessions de caisse par appareil (ouverture, mouvements d'espèces, clôture recalculée par le serveur) et rattacher ventes et retours synchronisés à leur session.

**Architecture:** Nouveau module `app/modules/cash_register/`, structure standard (router, service, repository, schemas, models, exceptions). Une migration Alembic ajoute `cash_sessions`, `cash_movements` (RLS, triggers) et `cash_session_id` sur `sales` et `sale_returns`. Les totaux viennent de `SaleService` et `ReturnService`, jamais de leurs repositories. La validation de session dans la synchronisation passe par `SyncService`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, PostgreSQL 16 (RLS), Alembic, Pydantic v2, pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-11-10-sessions-de-caisse-design.md`. Un plan Flutter séparé suivra, une fois ces contrats testés.

## Global Constraints

- Montants : `NUMERIC(12,2)` en base, `Decimal` en domaine, chaîne dans le JSON. Jamais de `float`.
- Les UUID des sessions et des mouvements sont générés par le client, sans défaut serveur.
- Lever uniquement des sous-classes des exceptions de `app/core/exceptions.py`, avec les codes `CASH_SESSION_ALREADY_OPEN` (409), `CASH_SESSION_CLOSED` (409), `INSUFFICIENT_CASH` (422) et `IDEMPOTENCY_CONFLICT` (409).
- Toutes les routes utilisent `TenantDbSession`, `CurrentStoreId` et `CurrentUserId`, avec le préfixe `/api/v1/cash-sessions`. `response_model` et `status_code` sont toujours explicites.
- Valeurs de `reason` : entrées `top_up`, `float`, `other` ; sorties `expense`, `withdrawal`, `supplies`, `other`. `note` est obligatoire si `reason = other`.
- `opened_at`, `created_at` et `closed_at` doivent porter un fuseau horaire et ne pas dépasser `now + 300 s` (même règle que `SaleCreate`).
- Avant chaque commit : `make format && make lint && make type-check`.
- Commits au format `type(scope): message` en français, **sans trailer `Co-Authored-By`** (mémoire utilisateur).
- Travail sur la branche `feat/cash-register-backend`, créée depuis `main` à jour.

## Review Focus

1. **Vente qui référence la session d'une autre boutique.** La vérification de clé étrangère ignore la RLS, donc l'insert passerait. `SyncService` doit vérifier la session sous RLS et répondre `failed`. Testé en Task 6.
2. **Retry de clôture après un timeout réseau, avec un payload identique.** La réponse doit être 200 avec la même clôture, et non 409. Testé en Task 5.
3. **Montants à décimales** (`"1500.50"`). L'écart doit être exact et `Decimal("0.00") == 0` doit valoir « équilibré ». Testé en Task 5.
4. **Session ouverte sans aucune opération.** Le solde est `opening_amount` et non `None` : les sommes vides valent 0. Testé en Task 2.
5. **Mouvement rejoué après la clôture alors qu'il avait été créé avant.** Il est accepté et apparaît dans `late_impact`. Testé en Task 4.

---

### Task 0: Branche, spec et ADR

**Files:**
- Create: `docs/adr/0015-sessions-de-caisse.md` (depuis `docs/adr/_template.md`)
- Modify: `docs/adr/README.md` (ajout de la ligne 0015)
- Add: `docs/superpowers/specs/2026-11-10-sessions-de-caisse-design.md` et ce plan

- [ ] **Step 1:** Exécuter `git stash -u && git checkout main && git pull && git checkout -b feat/cash-register-backend && git stash pop`. Résultat attendu : la spec et le plan sont présents sur la nouvelle branche.
- [ ] **Step 2:** Écrire l'ADR-0015 au statut « Accepté — 10 novembre 2026 ». Contexte, puis décisions D1–D4 et C1–C6 de la spec §2, alternatives (session par boutique, ventes hors session, réattribution à la session ouverte), conséquences (hors périmètre de la spec §10).
- [ ] **Step 3: Commit** `docs(adr): sessions de caisse par appareil (ADR-0015)`.

---

### Task 1: Migration et modèles

**Files:**
- Create: `alembic/versions/<rev>_add_cash_register.py` (`down_revision = "c4e8a2d6f1b3"` ; vérifier avec `uv run alembic heads`)
- Create: `app/modules/cash_register/__init__.py`, `app/modules/cash_register/models.py`
- Modify: `app/modules/sales/models.py` (colonne `cash_session_id`), `app/modules/returns/models.py` (idem), `alembic/env.py` (import des modèles)
- Test: `tests/test_cash_register.py` (nouveau)

**Interfaces:**
- Produit :
  - `CashSession` et `CashMovement` (SQLAlchemy), avec les colonnes exactes de la spec §4 ;
  - les constantes `SESSION_STATUSES = ("open", "closed")`, `MOVEMENT_TYPES = ("cash_in", "cash_out")`, `CASH_IN_REASONS`, `CASH_OUT_REASONS` ;
  - `Sale.cash_session_id: Mapped[UUID | None]` et `SaleReturn.cash_session_id: Mapped[UUID | None]`.

Contenu de la migration (modèle : `d1a4f7c2e9b0_add_customer_returns.py`) :
- Tables et CHECK de la spec §4, dont :
  - `chk_cash_sessions_state` : `open` ⇒ tous les champs de clôture sont NULL ; `closed` ⇒ ils sont tous NOT NULL et `discrepancy_amount = counted_amount - expected_amount` ;
  - `chk_cash_sessions_note_on_discrepancy` : `status <> 'closed' OR discrepancy_amount = 0 OR length(trim(closing_note)) > 0` ;
  - `chk_cash_movements_reason` : CHECK croisé type/reason.
- `CREATE UNIQUE INDEX uq_cash_sessions_open_per_device ON cash_sessions (store_id, device_id) WHERE status = 'open'`.
- Index `idx_cash_sessions_store_opened_at (store_id, opened_at DESC)`, `idx_cash_movements_session_id`, `idx_sales_cash_session_id` et `idx_sale_returns_cash_session_id` (partiels `WHERE cash_session_id IS NOT NULL`).
- RLS `rls_<table>_tenant_isolation` sur les deux tables (modèle `.claude/rules/migrations-safety.md`).
- Trigger `set_updated_at` sur `cash_sessions`.
- Fonction et trigger `prevent_closed_cash_session_modification` (BEFORE UPDATE OR DELETE). Ils lèvent une exception si `TG_OP = 'DELETE'` ou si `OLD.status = 'closed'`.
- Triggers d'immuabilité sur `cash_movements` : réutiliser la fonction existante utilisée pour `sale_returns`, en vérifiant son nom dans la migration des retours.
- Downgrade complet et inverse. Il est refusé (`RAISE EXCEPTION`) si `cash_sessions` contient des lignes.

- [ ] **Step 1: Tests DB qui échouent** dans `tests/test_cash_register.py`, avec les helpers `_create_user`, `_create_store` et `_headers` de `tests/test_sync.py`, et des inserts SQL via `db_session` :
  - `test_two_open_sessions_same_device_violate_unique_index` → `IntegrityError` ;
  - `test_open_sessions_on_two_devices_are_allowed` ;
  - `test_closed_session_cannot_be_updated` : `UPDATE … SET closing_note='x'` sur une session clôturée → `DBAPIError` ;
  - `test_cash_session_cannot_be_deleted` ;
  - `test_cash_movement_is_immutable` ;
  - `test_closed_with_discrepancy_requires_note` → `IntegrityError` ;
  - `test_cash_out_reason_must_match_type` : `type='cash_in', reason='expense'` → `IntegrityError`.
- [ ] **Step 2:** `uv run pytest tests/test_cash_register.py -v`. Résultat attendu : FAIL (`relation "cash_sessions" does not exist`).
- [ ] **Step 3:** Écrire la migration, les modèles et l'import dans `env.py`.
- [ ] **Step 4:** `uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`, puis les tests. Résultat attendu : PASS.
- [ ] **Step 5: Commit** `feat(cash): tables des sessions et mouvements de caisse`.

---

### Task 2: Calcul du solde

**Files:**
- Modify: `app/modules/sales/repository.py`, `app/modules/sales/service.py`, `app/modules/returns/repository.py`, `app/modules/returns/service.py`
- Create: `app/modules/cash_register/repository.py`, `app/modules/cash_register/schemas.py` (`CashSummary`), `app/modules/cash_register/service.py`
- Test: `tests/test_cash_register.py`

**Interfaces:**
- Produit :
  - `SaleService.cash_totals_for_session(session_id: UUID) -> SessionSalesTotals`. Il s'agit d'un dataclass défini dans `app/modules/sales/schemas.py`, avec les champs `cash: Decimal`, `cash_count: int` et `mobile_money: Decimal`. La part espèces est calculée en SQL avec `CASE payment_method WHEN 'cash' THEN total_amount WHEN 'mixed' THEN cash_amount ELSE 0 END`. La part mobile money vaut `total_amount − part espèces`. Une somme vide vaut 0 grâce à `COALESCE`.
  - `ReturnService.cash_refund_total_for_session(session_id: UUID) -> Decimal` : somme de `refund_amount` pour `refund_method = 'cash'`.
  - `CashSessionRepository` : `get_by_id`, `get_for_update`, `get_open_for_device(device_id)`, `insert_session(session) -> bool` (ON CONFLICT (id) DO NOTHING ; une violation de l'index partiel lève `IntegrityError`), `movement_totals(session_id) -> tuple[Decimal, Decimal]` (entrées, sorties), `list_movements(session_id)`, `get_movement(id)`, `insert_movement`, `list_page(device_id, cursor, limit)`.
  - `CashSummary` (Pydantic) : `opening_amount`, `cash_sales`, `cash_sales_count`, `mobile_money_sales`, `cash_in`, `cash_out`, `cash_refunds`, `expected_amount`, `late_impact`, `server_recalculated`.
  - `CashSessionService.compute_balance(session: CashSession) -> CashSummary`. Le solde suit la formule de la spec §3. Pour une session ouverte : `expected_amount` = solde courant, `late_impact = 0`. Pour une session clôturée : `expected_amount` = valeur figée, `late_impact` = recalcul − figé, `server_recalculated = expected_amount != client_expected_amount`.

- [ ] **Step 1: Tests qui échouent.** Chaque test crée une session ouverte (`opening_amount="10000"`) et des ventes via `SaleService.create_sale`, avec un payload `cash_session_id` posé directement sur le modèle. La synchronisation n'est branchée qu'en Task 6, d'ici là on passe par le service.
  - `test_balance_without_operations_is_opening_amount` : `expected_amount == Decimal("10000")`.
  - `test_cash_sale_counts_total` : vente `cash` à 3000 → 13000.
  - `test_mobile_money_sale_is_excluded` : `mobile_money_wave` à 5000 → 10000, `mobile_money_sales == 5000`.
  - `test_mixed_sale_counts_cash_part_only` : `mixed` à 8000 (`cash_amount` 3000, `mobile_money_amount` 5000) → 13000.
  - `test_cash_refund_decreases_and_mobile_refund_does_not` : retour `cash` de 1000 et retour `mobile_money_orange` de 500 sur des ventes de la session → `cash_refunds == 1000`.
  - `test_sales_of_another_session_are_ignored`.
- [ ] **Step 2:** Lancer les tests. Résultat attendu : FAIL.
- [ ] **Step 3:** Implémenter les méthodes ci-dessus. Pour que les tests passent, `SaleService.create_sale` et `ReturnService.create_return` doivent transmettre `cash_session_id` du payload au modèle, et `create_sale_atomic` doit l'ajouter à `.values(...)`. Le champ optionnel du payload est donc ajouté dès cette task (`SaleCreate.cash_session_id: UUID | None = None`, idem `SaleReturnCreate`).
- [ ] **Step 4:** Lancer les tests. Résultat attendu : PASS, ainsi que `tests/test_sales.py` et `tests/test_returns.py` toujours verts.
- [ ] **Step 5: Commit** `feat(cash): calcul du solde théorique d'une session`.

---

### Task 3: Ouvrir, session active, détail, historique

**Files:**
- Create: `app/modules/cash_register/router.py`, `app/modules/cash_register/exceptions.py`
- Modify: `app/modules/cash_register/schemas.py`, `app/modules/cash_register/service.py`, `app/main.py` (`include_router(cash_router, prefix=f"{api_v1_prefix}/cash-sessions", tags=["cash"])`)
- Test: `tests/test_cash_register.py`

**Interfaces:**
- Produit :
  - exceptions `CashSessionAlreadyOpenError(ConflictError)`, `CashSessionClosedError(ConflictError)`, `InsufficientCashError(ValidationError)`, `IdempotencyConflictError(ConflictError)`, chacune avec son attribut `code` ;
  - schémas `CashSessionOpen`, `CashSessionResponse`, `CashMovementResponse`, `CashSessionDetailResponse {session, summary, movements}` et `CashSessionPage = CursorPage[CashSessionResponse]`, aux champs exacts de la spec §5.1 et §5.8 ;
  - `CashSessionService.open(store_id, user_id, payload) -> tuple[CashSession, bool]`, `get_active(device_id) -> CashSessionDetailResponse`, `get_detail(session_id) -> CashSessionDetailResponse`, `list_page(device_id: UUID | None, cursor: str | None, limit: int) -> CashSessionPage` ;
  - routes : `POST ""` (201 ou 200 via `Response.status_code`), `GET "/active"`, `GET ""`, `GET "/{session_id}"`.
- Règles d'idempotence de `open` :
  - même `id` et mêmes `device_id`, `opening_amount` et `opened_at` → `(existant, False)` ;
  - même `id` avec un contenu différent → `IdempotencyConflictError` ;
  - `IntegrityError` sur `uq_cash_sessions_open_per_device` → rollback du SAVEPOINT (`begin_nested`), puis `CashSessionAlreadyOpenError`.

- [ ] **Step 1: Tests HTTP qui échouent** (`client`, `_headers`) :
  - `test_open_session_returns_201_and_retry_returns_200` ;
  - `test_open_with_same_id_different_amount_is_idempotency_conflict` → 409, `code == "IDEMPOTENCY_CONFLICT"` ;
  - `test_second_open_on_same_device_is_409_already_open` ;
  - `test_concurrent_opens_on_same_device_only_one_succeeds` : deux sessions DB via `db_engine` et `asyncio.gather`, comme `test_concurrent_returns_cannot_exceed_sold_quantity` ;
  - `test_get_active_returns_detail_or_404` ;
  - `test_history_is_paginated_newest_first` : 3 sessions, `limit=2` → `has_more`, puis `next_cursor` ;
  - `test_store_cannot_see_or_open_on_session_of_another_store` : GET détail → 404, et GET active/historique ne la listent pas ;
  - `test_negative_opening_amount_and_future_opened_at_are_422`.
- [ ] **Step 2:** Lancer les tests. Résultat attendu : FAIL (404 sur la route).
- [ ] **Step 3:** Implémenter.
- [ ] **Step 4:** Lancer les tests. Résultat attendu : PASS.
- [ ] **Step 5: Commit** `feat(cash): ouverture et consultation des sessions de caisse`.

---

### Task 4: Mouvements d'espèces

**Files:**
- Modify: `app/modules/cash_register/{schemas,service,router}.py`
- Test: `tests/test_cash_register.py`

**Interfaces:**
- Produit :
  - `CashMovementCreate {id, type, reason, amount (> 0), note, created_at}`, avec un validateur pour type/reason et la note obligatoire si `other` ;
  - `CashSessionService.record_movement(store_id, user_id, session_id, payload) -> tuple[CashMovement, bool]` ;
  - route `POST "/{session_id}/movements"` → 201 ou 200.
- Ordre de traitement :
  1. mouvement existant avec le même id → 200 s'il appartient à la même session et a le même montant et le même type, sinon `IdempotencyConflictError` ;
  2. `get_for_update(session_id)`, puis `NotFoundError` si absent ;
  3. session clôturée et `created_at > closed_at` → `CashSessionClosedError` ;
  4. `cash_out` sur une session ouverte, avec `amount > compute_balance().expected_amount` → `InsufficientCashError(field="amount")`. La règle ne s'applique pas à une session clôturée, car le mouvement est déjà fait ;
  5. insertion.

- [ ] **Step 1: Tests qui échouent** :
  - `test_cash_in_and_out_change_balance` : ouverture 10000, entrée 5000, sortie 3500 → 11500 ;
  - `test_cash_out_above_balance_is_422_insufficient_cash` ;
  - `test_cash_out_equal_to_balance_is_allowed` ;
  - `test_movement_retry_is_200_without_double_count` ;
  - `test_movement_after_closing_time_is_409_session_closed` ;
  - `test_movement_created_before_closure_arriving_late_is_accepted_and_in_late_impact` (Review Focus 5) ;
  - `test_other_reason_requires_note_and_amount_must_be_positive` → 422 ;
  - `test_movement_on_session_of_another_store_is_404`.
- [ ] **Step 2:** FAIL attendu. **Step 3:** implémenter. **Step 4:** PASS attendu.

  Pour les tests qui ont besoin d'une session clôturée avant la Task 5 : écrire l'état clôturé via `UPDATE` SQL (session ouverte → clôturée, autorisé par le trigger), ou bien placer ces deux tests en Task 5 si c'est plus simple.
- [ ] **Step 5: Commit** `feat(cash): entrées et sorties d'espèces`.

---

### Task 5: Clôture

**Files:**
- Modify: `app/modules/cash_register/{schemas,service,router}.py`
- Test: `tests/test_cash_register.py`

**Interfaces:**
- Produit :
  - `CashSessionClose {counted_amount (≥ 0), client_expected_amount (≥ 0, optionnel), closing_note, closed_at}` ;
  - `CashSessionService.close(store_id, user_id, session_id, payload) -> CashSessionDetailResponse` ;
  - route `POST "/{session_id}/close"` → 200.
- Algorithme : spec §5.6, étapes 1 à 5.
  - L'idempotence compare `counted_amount` et `closed_at` (égalité de `Decimal` et de `datetime`).
  - Un écart non nul sans note donne `ValidationError(field="closing_note")`.
  - Ajouter aussi `closed_at < opened_at` → `ValidationError(field="closed_at")`.
  - `closure_recorded_at` prend `func.now()`.

- [ ] **Step 1: Tests qui échouent** :
  - `test_close_balanced_session` : compté = solde → `discrepancy_amount == 0`, `status == "closed"` ;
  - `test_close_with_shortage_requires_note` : sans note → 422 `field == "closing_note"`, avec note → `discrepancy_amount == Decimal("-500")` ;
  - `test_close_with_surplus_and_decimal_amounts` : solde 1500.50, compté 1600.00 → +99.50 (Review Focus 3) ;
  - `test_server_ignores_client_expected_amount` : `client_expected_amount` faux → `expected_amount` serveur et `server_recalculated is True` ;
  - `test_close_retry_with_same_payload_returns_200_same_result` (Review Focus 2) ;
  - `test_second_close_with_different_count_is_409_session_closed` ;
  - `test_sale_after_closure_is_in_late_impact_not_in_expected` : créer une vente sur la session clôturée via le service → `expected_amount` inchangé, `late_impact == 3000` ;
  - `test_close_concurrent_with_sale_insert_counts_it_or_reports_it_late` : `asyncio.gather` sur deux sessions DB → `expected_amount + late_impact` vaut toujours le solde complet ;
  - `test_close_session_of_another_store_is_404`.
- [ ] **Step 2:** FAIL attendu. **Step 3:** implémenter. **Step 4:** PASS attendu.
- [ ] **Step 5: Commit** `feat(cash): clôture atomique et idempotente des sessions`.

---

### Task 6: Synchronisation des ventes et retours

**Files:**
- Modify: `app/modules/sales/schemas.py` (`SaleResponse.cash_session_id`), `app/modules/returns/schemas.py` (`SaleReturnResponse.cash_session_id`), `app/modules/sync/service.py`, `app/modules/cash_register/service.py`
- Test: `tests/test_cash_register.py`

**Interfaces:**
- Consomme : `CashSessionService.exists(session_id: UUID) -> bool`, une lecture soumise à la RLS, ajoutée dans cette task.
- Comportement dans `SyncService.sync_sales_batch` et `sync_returns_batch` : si `payload.cash_session_id` est renseigné et que `exists()` renvoie False, le résultat est `failed` avec `error="cash session not found"`. On n'appelle pas `create_*`, et on n'utilise pas `rejected`, car l'ouverture peut arriver plus tard.

- [ ] **Step 1: Tests qui échouent** (via `POST /api/v1/sync/sales` et `/sync/returns`) :
  - `test_synced_sale_is_attached_and_counted` ;
  - `test_sale_resent_three_times_counts_once` ;
  - `test_sale_with_unknown_session_fails_then_succeeds_after_open` ;
  - `test_sale_with_session_of_another_store_fails` (Review Focus 1) ;
  - `test_sale_without_session_still_accepted` (ancienne version de l'app) ;
  - `test_cash_return_synced_after_closure_shows_in_late_impact` ;
  - `test_pull_exposes_cash_session_id_on_sales_and_returns`.
- [ ] **Step 2:** FAIL attendu. **Step 3:** implémenter. **Step 4:** PASS attendu, avec toute la suite `make test` verte.
- [ ] **Step 5: Commit** `feat(sync): rattacher ventes et retours à leur session de caisse`.

---

### Task 7: Documentation et vérification finale

**Files:**
- Modify: `docs/api.md` (section « Sessions de caisse » : les 6 routes, payloads et réponses de la spec §5, codes d'erreur, champ `cash_session_id` en synchronisation), `docs/data-model.md` et `docs/data-model-detailed.md` (2 tables, 2 colonnes, triggers, index partiel), `CLAUDE.md` (ligne `modules/cash_register/` dans « Key files »)

- [ ] **Step 1:** Rédiger la documentation, avec les exemples JSON repris de la spec §5.8.
- [ ] **Step 2:** `make format && make lint && make type-check && make test`. Résultat attendu : tout est vert et la couverture de `app/modules/cash_register` est ≥ 70 % (`make test-cov`).
- [ ] **Step 3:** Vérifier une dernière fois que `alembic downgrade -1` puis `upgrade head` passent sur une base de dev.
- [ ] **Step 4: Commit** `docs(cash): API et modèle de données des sessions de caisse`, puis ouvrir la PR vers `main` après accord de l'utilisateur.
