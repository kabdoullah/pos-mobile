# Sessions de caisse — conception

Date : 2026-11-10 · Dépôts : `pos-mobile` (backend FastAPI) et `pos-mobile-app` (Flutter)

## 1. Intention

Le commerçant doit savoir à tout moment combien d'espèces devraient se trouver dans son tiroir, compter en fin de session ce qui s'y trouve réellement, et garder une trace fiable de l'écart. Le calcul s'appuie sur les ventes et retours existants, sans les réimplémenter, et fonctionne hors ligne.

**Anti-objectifs** (ce qui serait un échec même si « ça marche ») :
- un paiement mobile money compté dans le tiroir ;
- une vente, un retour ou un mouvement compté deux fois après un retry ;
- une clôture modifiée après coup sans que le commerçant le voie ;
- un parcours de vente ou de retour réécrit.

## 2. Décisions

### Validées par le commerçant (2026-11-10)

| # | Sujet | Décision |
|---|-------|----------|
| D1 | Périmètre | **Une session ouverte par téléphone.** Chaque appareil est un tiroir, identifié par un `device_id`. |
| D2 | Vente sans caisse | **Interdite dans l'app.** Encaisser exige une session ouverte. Le serveur accepte toujours les ventes sans session (anciennes versions). |
| D3 | Sortie > solde | **Refusée** par l'app et par le serveur (`INSUFFICIENT_CASH`). |
| D4 | Opération arrivée après clôture | **Rattachée à sa session d'origine et signalée.** La clôture reste figée. L'impact apparaît séparément. |

### Héritées du projet

- **Un seul utilisateur par boutique** (`stores.owner_id` unique). Il n'existe ni rôles ni comptes caissiers. La permission est donc : « la session appartient à la boutique du JWT » (RLS), et le caissier est l'utilisateur du JWT.
- Montants : `NUMERIC(12,2)` en base, `Decimal` en domaine, `String` dans les DTO.
- Synchronisation événementielle par UUID client (ADR-0003, ADR-0010).
- Un remboursement est confirmé au comptoir (ADR-0010). Un retour `refund_method = cash` signifie donc des espèces réellement sorties.

### Prises par moi (à relire)

- **C1. Montant d'ouverture.** Il est stocké sur la session (`opening_amount`), pas comme mouvement, pour ne pas dupliquer l'information.
- **C2. Pas de `reference_id` sur les mouvements.** L'UUID client du mouvement est sa référence unique. Ventes et retours portent eux-mêmes `cash_session_id` au lieu d'être recopiés en mouvements.
- **C3. Remboursement espèces supérieur au solde : non bloqué.** Le parcours de retour reste inchangé. Le solde peut devenir négatif et un avertissement s'affiche. D3 ne s'applique qu'aux sorties manuelles.
- **C4. Retour rejeté par le serveur.** Il n'existe pas côté serveur, donc il n'est pas compté dans le solde serveur. L'app affiche « Retour refusé : X FCFA rendus non comptés », ce qui explique le déficit (cohérent avec la régularisation manuelle de l'ADR-0010).
- **C5. Impact après clôture.** Il est calculé à la lecture (`recalcul actuel − expected_amount figé`), jamais écrit dans la session clôturée.
- **C6. Remboursement en espèces sans caisse ouverte.** L'app demande d'ouvrir la caisse (comme pour une vente). Un remboursement mobile money n'en a pas besoin.

## 3. Règles métier

### Solde théorique

```
solde = opening_amount
      + Σ part espèces des ventes de la session
      + Σ entrées (cash_in)
      − Σ sorties (cash_out)
      − Σ refund_amount des retours de la session avec refund_method = 'cash'
```

**Part espèces d'une vente** :

| payment_method | part espèces |
|---|---|
| `cash` | `total_amount` |
| `mobile_money_*` | 0 |
| `mixed` | `cash_amount` (le serveur garantit `cash_amount + mobile_money_amount = total_amount`) |

Le rendu de monnaie n'entre pas en compte : `total_amount` est ce qui reste dans le tiroir.

**Écart** : `discrepancy_amount = counted_amount − expected_amount`. Il vaut 0 si la caisse est équilibrée, il est positif en cas d'excédent et négatif en cas de déficit.

L'app et le serveur appliquent la même formule. Le serveur fait foi (§6.4).

### Cycle de vie

`open → closed`, sans retour possible. Une session clôturée n'est jamais rouverte ni modifiée (trigger PostgreSQL).

### Rattachement

- **Vente** : rattachée à la session ouverte de l'appareil au moment de la vente (`cash_session_id` posé localement, envoyé avec la vente).
- **Retour** : rattaché à la session ouverte de l'appareil qui rembourse, même si la vente vient d'un autre appareil. C'est là que l'argent est sorti.
- Le serveur ne réattribue jamais une opération : il garde la session envoyée par l'app.

### Opérations reçues après la clôture

Règle unique, fondée sur l'horloge client :

- **vente ou retour** : toujours accepté et rattaché à sa session, même clôturée (l'argent a bougé). Il n'est pas compté dans `expected_amount`, qui est figé. Il apparaît dans l'impact après clôture.
- **mouvement** créé avant `closed_at` : accepté et signalé de la même façon.
- **mouvement** créé après `closed_at` : refusé (`CASH_SESSION_CLOSED`).

L'app limite fortement ces cas : elle n'envoie la clôture qu'une fois toutes les opérations de la session acquittées (§7.3).

## 4. Modèle de données backend

Nouveau module `app/modules/cash_register/`, structure standard (router, service, repository, schemas, models, exceptions).

### `cash_sessions` (tenant, RLS)

| Colonne | Type | Contrainte / rôle |
|---|---|---|
| `id` | UUID PK | généré par l'app, pas de défaut serveur |
| `store_id` | UUID NOT NULL | FK stores RESTRICT, index |
| `device_id` | UUID NOT NULL | tiroir (D1) |
| `status` | VARCHAR(10) NOT NULL | CHECK `open`/`closed` |
| `opening_amount` | NUMERIC(12,2) NOT NULL | ≥ 0 |
| `opening_note` | VARCHAR(500) NULL | |
| `opened_at` | TIMESTAMPTZ NOT NULL | horloge client |
| `opened_by` | UUID NULL | FK users SET NULL |
| `expected_amount` | NUMERIC(12,2) NULL | calculé par le serveur à la clôture |
| `client_expected_amount` | NUMERIC(12,2) NULL | ce que l'app avait affiché (traçabilité) |
| `counted_amount` | NUMERIC(12,2) NULL | ≥ 0 |
| `discrepancy_amount` | NUMERIC(12,2) NULL | counted − expected |
| `closing_note` | VARCHAR(500) NULL | obligatoire si écart ≠ 0 (contrainte CHECK) |
| `closed_at` | TIMESTAMPTZ NULL | horloge client |
| `closed_by` | UUID NULL | FK users SET NULL |
| `closure_recorded_at` | TIMESTAMPTZ NULL | horloge serveur de la clôture |
| `created_at`, `updated_at` | TIMESTAMPTZ | trigger `update_updated_at_column` |

Contraintes :
- CHECK de cohérence : `open` implique que tous les champs de clôture sont NULL ; `closed` implique qu'ils sont tous renseignés et que `discrepancy_amount = counted_amount − expected_amount`.
- CHECK `closed_at >= opened_at`.
- **Index unique partiel `(store_id, device_id) WHERE status = 'open'`.** Il garantit une seule session ouverte par appareil, y compris face à deux requêtes concurrentes.
- Index `(store_id, opened_at DESC)` pour l'historique.
- Trigger `prevent_closed_cash_session_modification` : refuse tout UPDATE d'une ligne déjà `closed`, et tout DELETE.

### `cash_movements` (tenant, RLS, immuable)

| Colonne | Type | Contrainte |
|---|---|---|
| `id` | UUID PK | généré par l'app |
| `store_id` | UUID NOT NULL | FK, index |
| `session_id` | UUID NOT NULL | FK cash_sessions RESTRICT, index |
| `type` | VARCHAR(10) | `cash_in` / `cash_out` |
| `reason` | VARCHAR(20) | entrée : `top_up`, `float`, `other` ; sortie : `expense`, `withdrawal`, `supplies`, `other` (CHECK croisé avec type) |
| `amount` | NUMERIC(12,2) | > 0 |
| `note` | VARCHAR(500) NULL | obligatoire si `reason = 'other'` |
| `created_at` | TIMESTAMPTZ | horloge client |
| `created_by` | UUID NULL | FK users SET NULL |
| `synced_at` | TIMESTAMPTZ | `now()` serveur |

Trigger d'immuabilité (UPDATE/DELETE refusés), comme `sales`.

### Colonnes ajoutées

- `sales.cash_session_id UUID NULL`, FK cash_sessions RESTRICT, index partiel `WHERE cash_session_id IS NOT NULL`.
- `sale_returns.cash_session_id UUID NULL`, même chose.

Ces colonnes sont posées à l'INSERT. Les triggers d'immuabilité ne sont pas touchés, et les lignes existantes restent NULL (hors session).

### Migration

Une seule migration `cash_register`. Elle crée les deux tables, la RLS, les triggers et les index, et ajoute les deux colonnes. Le downgrade est complet. Il est refusé si des sessions existent, sur le modèle de la migration des retours. Les nouveaux modèles sont importés dans `alembic/env.py`.

### Découplage entre modules

- `cash_register.service` lit les totaux via de nouvelles méthodes de `SaleService` (`cash_total_for_session`) et de `ReturnService` (`cash_refund_total_for_session`). Il n'importe jamais leurs repositories.
- La validation de la session lors de la synchronisation d'une vente ou d'un retour se fait dans `SyncService`, qui appelle `CashSessionService`. Cela évite un import circulaire entre ventes et caisse.

## 5. API

Préfixe `/api/v1/cash-sessions`, routes authentifiées (`TenantDbSession`). Les erreurs suivent le format existant `{detail, code, field}`. Les montants sont des chaînes dans les réponses (sérialisation `Decimal` existante).

Codes métier (sous-classes des exceptions de `core/exceptions.py`) :

| code | HTTP | sens |
|---|---|---|
| `CASH_SESSION_ALREADY_OPEN` | 409 | l'appareil a déjà une autre session ouverte |
| `CASH_SESSION_CLOSED` | 409 | session clôturée (mouvement postérieur, ou clôture différente déjà enregistrée) |
| `INSUFFICIENT_CASH` | 422 | sortie supérieure au solde |
| `IDEMPOTENCY_CONFLICT` | 409 | même UUID, contenu différent |
| `NOT_FOUND` | 404 | session inconnue ou d'une autre boutique (RLS) |
| `VALIDATION_ERROR` | 422 | payload invalide |

### 5.1 Ouvrir — `POST /api/v1/cash-sessions`

```json
{
  "id": "6f1c…",
  "device_id": "a2b9…",
  "opening_amount": "25000",
  "opening_note": "Fond de caisse lundi",
  "opened_at": "2026-11-10T07:58:12Z"
}
```

- **201** : session créée.
- **200** : le même `id` existe déjà avec le même contenu (retry).
- Le corps de réponse est `CashSessionResponse` (§5.8).
- Erreurs : `CASH_SESSION_ALREADY_OPEN` (index partiel violé), `IDEMPOTENCY_CONFLICT`, `VALIDATION_ERROR` (montant négatif, `opened_at` plus de 5 min dans le futur, comme les ventes).

### 5.2 Session active — `GET /api/v1/cash-sessions/active?device_id=…`

- **200** : `CashSessionDetailResponse`.
- **404** : aucune session ouverte pour cet appareil.

### 5.3 Détail et résumé — `GET /api/v1/cash-sessions/{id}`

**200** : `CashSessionDetailResponse`, qui contient la session, le résumé et les mouvements.

### 5.4 Historique — `GET /api/v1/cash-sessions?cursor=&limit=50&device_id=`

**200** : `CursorPage[CashSessionResponse]`, trié par `opened_at` décroissant (pagination existante `app/core/pagination.py`).

### 5.5 Mouvement — `POST /api/v1/cash-sessions/{id}/movements`

```json
{
  "id": "0d4e…",
  "type": "cash_out",
  "reason": "supplies",
  "amount": "3500",
  "note": "Sachets",
  "created_at": "2026-11-10T11:20:00Z"
}
```

Traitement : la session est verrouillée (`FOR UPDATE`). Si elle est clôturée et que `created_at > closed_at`, la réponse est `CASH_SESSION_CLOSED`. Pour une sortie, le solde est recalculé et une sortie supérieure au solde donne `INSUFFICIENT_CASH`. Le mouvement est ensuite inséré.

- **201** : mouvement créé.
- **200** : retry du même `id`.
- Le corps de réponse est `CashMovementResponse`.

### 5.6 Clôturer — `POST /api/v1/cash-sessions/{id}/close`

```json
{
  "counted_amount": "61500",
  "client_expected_amount": "62000",
  "closing_note": "Manque 500, monnaie rendue en trop",
  "closed_at": "2026-11-10T19:02:40Z"
}
```

Traitement, dans une seule transaction :

1. Verrouiller la session (`SELECT … FOR UPDATE`).
2. Si elle est déjà clôturée avec les mêmes `counted_amount` et `closed_at`, répondre **200** avec la clôture existante (idempotence). Si les valeurs diffèrent, répondre `CASH_SESSION_CLOSED`.
3. Recalculer `expected_amount` à partir des lignes en base. La valeur `client_expected_amount` n'est jamais utilisée pour le calcul.
4. Calculer `discrepancy_amount`. Exiger `closing_note` si l'écart est différent de 0 (sinon `VALIDATION_ERROR`, `field: closing_note`).
5. Écrire la clôture : `status = closed`, `closure_recorded_at = now()`, `closed_by` = utilisateur.

**200** : `CashSessionDetailResponse`. Le champ `summary.server_recalculated` vaut `true` si `expected_amount ≠ client_expected_amount`.

Une vente insérée en même temps prend un verrou `KEY SHARE` via la clé étrangère, qui entre en conflit avec le `FOR UPDATE`. Elle est donc soit comptée (commit avant la clôture), soit hors du montant figé et visible dans l'impact après clôture (commit après).

### 5.7 Synchronisation des ventes et retours

- `SaleCreate` et `SaleReturnCreate` reçoivent un champ optionnel `cash_session_id`. Il est absent pour les anciennes versions de l'app, ce qui correspond à NULL.
- **Session inconnue du serveur** : la vente ou le retour sort en `failed`, donc réessayable (l'ouverture n'est peut-être pas encore arrivée). L'opération n'est jamais rejetée pour une raison de session.
- **Session clôturée** : l'opération est acceptée (D4).
- `SaleResponse` et `SaleReturnResponse` exposent `cash_session_id`. Le pull `/sync/changes` les transmet donc sans nouvelle phase.

### 5.8 Réponses

```json
// CashSessionResponse
{
  "id": "6f1c…", "device_id": "a2b9…", "status": "closed",
  "opening_amount": "25000", "opening_note": "Fond de caisse lundi",
  "opened_at": "2026-11-10T07:58:12Z", "opened_by": "…",
  "expected_amount": "62000", "client_expected_amount": "62000",
  "counted_amount": "61500", "discrepancy_amount": "-500",
  "closing_note": "Manque 500…", "closed_at": "2026-11-10T19:02:40Z", "closed_by": "…"
}

// CashSessionDetailResponse
{
  "session": { /* CashSessionResponse */ },
  "summary": {
    "opening_amount": "25000",
    "cash_sales": "48000", "cash_sales_count": 23,
    "mobile_money_sales": "31000",
    "cash_in": "5000", "cash_out": "14500",
    "cash_refunds": "2000",
    "expected_amount": "61500",
    "late_impact": "0",
    "server_recalculated": false
  },
  "movements": [ /* CashMovementResponse, ordre décroissant */ ]
}
```

- Pour une session ouverte, `summary.expected_amount` est le solde courant.
- Pour une session clôturée, c'est le montant figé, et `late_impact = recalcul actuel − figé`.
- `mobile_money_sales` est fourni à titre informatif et n'entre jamais dans le solde.

## 6. Garanties serveur

1. **Une seule session ouverte par appareil** : index unique partiel. Une violation d'intégrité donne 409 `CASH_SESSION_ALREADY_OPEN`.
2. **Session clôturée intouchable** : contrôle applicatif et trigger.
3. **Aucun double comptage** : UUID client sur sessions, mouvements, ventes et retours. Un retry renvoie l'existant.
4. **Le serveur fait foi** : à la clôture, `expected_amount` est recalculé en base. L'app remplace sa valeur locale par celle du serveur. Si elles diffèrent, l'app l'affiche (« Montant recalculé par le serveur : … ») au lieu de corriger en silence.
5. **Isolation** : la RLS sur les deux tables. Une session d'une autre boutique donne 404.

## 7. App Flutter

### 7.1 Drift (schemaVersion 9 → 10)

- Nouvelle table `CashSessions` : colonnes miroir du serveur, plus `syncStatus` (`pending`, `synced`, `rejected`) et `rejectionCode`. Les montants sont en `TextColumn`.
- Nouvelle table `CashMovements` : même principe, avec `syncStatus`.
- `Sales` reçoit `cashAmount`, `mobileMoneyAmount` (TEXT nullable) et `cashSessionId`. Cela corrige l'absence locale de la répartition d'un paiement mixte. Le pull les remplit pour les ventes venant du serveur.
- `SaleReturns` reçoit `cashSessionId`.
- Aucun backfill n'est nécessaire : les ventes antérieures n'appartiennent à aucune session.

### 7.2 Feature `cash_register/`

Elle suit les couches domain, data, providers et presentation (`.claude/rules/mobile-conventions.md`).

- **domain** :
  - entités `CashSession`, `CashMovement`, `CashSummary` (en `Decimal`) ;
  - `CashBalanceCalculator`, en Dart pur, avec la même formule et les mêmes cas de test que le serveur ;
  - use cases `OpenCashSession`, `RecordCashMovement`, `CloseCashSession`, `WatchActiveSession`, `GetSessionHistory`, `GetSessionDetail`.
- **data** : repository Drift (transaction locale avec ajout dans `sync_queue`, comme `createSale`), datasource Retrofit, DTO freezed identiques au §5.8.
- **Identifiant d'appareil** : un UUID créé au premier lancement et conservé hors des données métier. Il ne doit pas être effacé par `wipeBusinessData`. L'emplacement est choisi par le builder.

### 7.3 Synchronisation

- Nouveaux types de file :
  - `cash_session_open` ;
  - `cash_movement` ;
  - `cash_session_close`.
- Ordre d'envoi dans `SyncOrchestrator` :
  1. ouvertures ;
  2. ventes ;
  3. retours ;
  4. mouvements ;
  5. clôtures ;
  6. catégories ;
  7. produits.
- **La clôture d'une session n'est envoyée que s'il ne reste aucune vente, retour ou mouvement de cette session en `pending` ou `failed`.**
- Conflits :
  - `CASH_SESSION_ALREADY_OPEN` sur une ouverture : impossible en usage normal (une session par appareil). L'entrée est marquée `rejected` et l'app affiche la session serveur.
  - `INSUFFICIENT_CASH` sur une sortie : `rejected`, visible dans la session.
  - `CASH_SESSION_CLOSED` sur une clôture : `rejected`, et l'app recharge la clôture serveur.
- **Déconnexion ou effacement des données locales** : bloqués tant qu'une session est ouverte ou qu'une opération de caisse attend sa synchronisation. Sinon, une session resterait ouverte sur le serveur sans appareil pour la fermer.

### 7.4 Intégration à la vente et aux retours (sans réécriture)

- **Vente** : avant l'encaissement, `sales_providers` lit la session active. S'il n'y en a pas, une feuille « Ouvrir la caisse » s'ouvre (D2). `createSale` reçoit `cashSessionId` et l'écrit dans la vente et dans le payload.
- **Retour** : `create_sale_return_usecase` reçoit `cashSessionId` de la session active. Un remboursement `cash` sans session renvoie vers l'ouverture (C6). Le reste du parcours est inchangé.

### 7.5 Écrans

Les écrans suivent le design system existant (Cacao & Or, AppSpacing, AppTypography, AppSemanticColors, mode sombre). Le bottom navigation ne change pas. L'accès se fait par une carte « Caisse » sur l'accueil (solde théorique ou « Caisse fermée »).

- **Caisse active** (`/cash`) : solde théorique mis en avant, détail de la formule, derniers mouvements, boutons Entrée, Sortie et Clôturer.
- **Ouverture** (`/cash/open`) : montant initial et commentaire.
- **Entrée et sortie** : feuilles modales avec montant, motif et commentaire (obligatoire si « Autre »).
- **Clôture** (`/cash/close`) :
  - récapitulatif et saisie du montant compté ;
  - état équilibré, excédent ou déficit ;
  - commentaire obligatoire si l'écart est différent de 0 ;
  - écran de confirmation avant validation.
- **Historique** (`/cash/history`) : sessions locales hors ligne, et liste serveur en ligne (tous appareils).
- **Détail d'une session clôturée** (`/cash/sessions/:id`) : avertissements « recalculé par le serveur », « opérations arrivées après clôture » et « retour refusé ».

## 8. Tests

**Backend** (pytest, vraie base `pos_test`, rôle `pos_app` non superuser) :

- **Ouverture** : création, retry idempotent, `IDEMPOTENCY_CONFLICT`, deux ouvertures concurrentes sur le même appareil (une seule passe), deux appareils en parallèle (les deux passent).
- **Solde** : ventes `cash`, mobile money (exclues), `mixed` (part espèces seule), entrées et sorties, retours `cash` et mobile money.
- **Sorties** : sortie supérieure au solde refusée.
- **Clôture** :
  - calcul de l'écart et commentaire obligatoire ;
  - `client_expected_amount` faux, donc valeur serveur retenue ;
  - double clôture identique (200) et double clôture différente (409) ;
  - clôture concurrente d'une insertion de vente.
- **Après clôture** : mouvement postérieur refusé ; vente et retour tardifs acceptés et visibles dans `late_impact`, clôture inchangée ; triggers d'immuabilité.
- **Synchronisation** : vente avec session inconnue en `failed`, puis `created` une fois la session ouverte ; ventes rejouées sans double comptage.
- **Isolation** : RLS entre boutiques sur les deux tables et sur toutes les routes (404).
- **Migration** : upgrade et downgrade testés.

**Flutter** (mocktail, Drift en mémoire) :
- `CashBalanceCalculator` sur les mêmes cas que le serveur ;
- migration v9 → v10 ;
- use cases (ouverture, sortie supérieure au solde, clôture et écart) ;
- ordre de la file et blocage de la clôture tant que des opérations sont en attente ;
- mapping des DTO ;
- vente bloquée sans session ;
- retour qui porte la session ;
- widgets de clôture (équilibré, excédent, déficit, commentaire requis).

## 9. Documentation

- Nouvel ADR-0015 « Sessions de caisse » qui reprend D1–D4 et C1–C6.
- Mise à jour de `docs/api.md`, `docs/data-model.md` et `docs/data-model-detailed.md`.
- Mise à jour du README des features côté app si nécessaire.

## 10. Hors périmètre (v1)

- **Clôture à distance d'une session restée ouverte** sur un appareil perdu ou réinstallé. Elle reste visible dans l'historique comme « ouverte ».
- Rôles ou comptes caissiers multiples.
- Contrepassation d'un mouvement.
- Impression du ticket de clôture.
