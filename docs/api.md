# API

> Conventions et lien vers la doc auto-générée. Dernière mise à jour : 29 avril 2026.

## Documentation interactive auto-générée

FastAPI génère automatiquement une documentation interactive (Swagger UI) qui liste tous les endpoints avec leurs schémas de requête et réponse.

| Environnement | URL Swagger | URL ReDoc |
|---|---|---|
| Local | http://localhost:8000/docs | http://localhost:8000/redoc |
| Production | https://api.pos-mobile-ci.com/docs | https://api.pos-mobile-ci.com/redoc |

**Cette documentation auto-générée est la référence exhaustive.** Le document que tu lis ici contient uniquement les conventions transverses, pas la liste détaillée des endpoints.

## Conventions générales

### Préfixe d'API et versioning

Tous les endpoints sont préfixés par `/api/v1/`. Exemple : `POST /api/v1/auth/login`.

Le versioning par numéro entier dans l'URL permet de faire évoluer l'API en cassant la compatibilité sans casser les clients existants. Quand on aura un `v2`, les deux versions cohabiteront pendant la migration.

### Format de données

- Toujours JSON (`Content-Type: application/json`)
- UTF-8
- Dates au format ISO 8601 avec timezone : `2026-04-29T14:30:00+00:00`
- Montants en string décimal pour préserver la précision : `"1500.00"` (pas `1500.00` en number JSON)

### Authentification

Toutes les routes sauf `/auth/register`, `/auth/login`, `/auth/forgot-password`, `/auth/reset-password` et `/health` requièrent un header :

```
Authorization: Bearer <jwt_token>
```

Le token est obtenu via `POST /api/v1/auth/login`. Sa durée de vie est de 1 heure. Pour le renouveler sans ressaisir le mot de passe, utiliser le refresh token via `POST /api/v1/auth/refresh`.

### Codes de retour

| Code | Signification | Quand |
|---|---|---|
| 200 | OK | GET réussi, action réussie |
| 201 | Created | POST qui crée une ressource |
| 204 | No Content | DELETE réussi |
| 400 | Bad Request | Payload invalide (validation Pydantic) |
| 401 | Unauthorized | JWT manquant, invalide ou expiré |
| 403 | Forbidden | JWT valide mais pas les droits |
| 404 | Not Found | Ressource inexistante ou hors tenant |
| 409 | Conflict | Conflit de sync (état serveur plus récent) |
| 422 | Unprocessable Entity | Payload syntaxiquement valide mais sémantiquement faux |
| 429 | Too Many Requests | Rate limit dépassé |
| 500 | Internal Server Error | Bug serveur |

### Format des erreurs

Toutes les erreurs suivent un format unifié :

```json
{
  "detail": "Message lisible par un humain",
  "code": "PRODUCT_NOT_FOUND",
  "field": "product_id"
}
```

Le champ `code` est un identifiant stable côté client pour i18n et logique conditionnelle. Le champ `field` est présent uniquement pour les erreurs de validation.

Certaines erreurs ajoutent une clé `details` (objet). Exemple : `STORE_SUSPENDED` (403, boutique suspendue, renvoyée par le login, le refresh et toute route authentifiée) :

```json
{
  "detail": "Store is suspended.",
  "code": "STORE_SUSPENDED",
  "field": null,
  "details": {
    "support_contact": "support@example.com",
    "support_whatsapp": "+2250700000000"
  }
}
```

`support_contact` vaut `""` si `SUPPORT_CONTACT` n'est pas configurée ; `support_whatsapp` (numéro avec indicatif pays) vaut `""` si `SUPPORT_WHATSAPP` n'est pas configurée. Les autres erreurs n'ont pas de clé `details`.

### Pagination

Les endpoints qui retournent des listes utilisent une pagination par cursor :

```
GET /api/v1/sales?limit=50&cursor=<opaque_token>
```

Réponse :

```json
{
  "items": [...],
  "next_cursor": "<opaque_token_or_null>",
  "has_more": true
}
```

Pourquoi cursor plutôt qu'offset/limit : les ventes sont insérées en flux continu, l'offset deviendrait incorrect si une vente est insérée pendant la pagination. Le cursor garantit la cohérence.

### Idempotence

Tous les endpoints `POST` qui créent des ressources synchronisées (notamment `/sync/sales`) acceptent un UUID v4 généré par le client comme identifiant. Le serveur fait un `INSERT ON CONFLICT DO NOTHING` côté DB.

Conséquence : un retry après timeout réseau ne crée pas de doublon.

## Endpoints clés (vue d'ensemble)

Liste non exhaustive des endpoints principaux. Voir Swagger pour les schémas complets.

### Authentification

```
POST   /api/v1/auth/register             Créer un compte
POST   /api/v1/auth/login                Obtenir un JWT
POST   /api/v1/auth/refresh              Renouveler un JWT
POST   /api/v1/auth/forgot-password      Demander un email de reset
POST   /api/v1/auth/reset-password       Confirmer le reset avec token
POST   /api/v1/auth/verify-email         Confirmer l'email avec token
GET    /api/v1/auth/me                   Profil de l'utilisateur connecté
```

### Profil

```
GET    /api/v1/users/me                   Mon profil (téléphone, email, display_name)
PATCH  /api/v1/users/me                   Nom affiché « Vendeur : … » sur les reçus (vide = retiré)
DELETE /api/v1/users/me                   Supprimer le compte et toutes les données de la boutique (body {password}, 403 si faux, ADR-0011)
```

### Boutique

```
GET    /api/v1/stores/me                  Récupérer ma boutique
PATCH  /api/v1/stores/me                  Mettre à jour ma boutique
PUT    /api/v1/stores/me/logo             Définir le logo (multipart, champ `file`)
GET    /api/v1/stores/me/logo             Logo WebP (ETag, 304 si If-None-Match)
DELETE /api/v1/stores/me/logo             Retirer le logo
```

`phone` (E.164, ex. `+2250700000000`) est imprimé sur les reçus. Le reçu PDF
(`GET /api/v1/sales/{id}/receipt`) affiche aussi le logo et « Vendeur : … »
(nom affiché de l'utilisateur qui a synchronisé la vente, `sales.created_by` ;
absent pour les ventes antérieures).

### Catalogue

```
GET    /api/v1/products                  Lister les produits (paginé)
POST   /api/v1/products                  Créer un produit
GET    /api/v1/products/{id}             Récupérer un produit
PATCH  /api/v1/products/{id}             Mettre à jour un produit
DELETE /api/v1/products/{id}             Soft delete un produit
GET    /api/v1/products/by-barcode/{ean} Recherche par code-barres
PUT    /api/v1/products/{id}/image       Définir l'image (multipart, champ `file`)
GET    /api/v1/products/{id}/image       Image WebP (ETag, 304 si If-None-Match)
DELETE /api/v1/products/{id}/image       Retirer l'image
GET    /api/v1/categories                Lister les catégories actives (par nom)
POST   /api/v1/categories                Créer une catégorie (409 si nom déjà pris)
PATCH  /api/v1/categories/{id}           Renommer une catégorie
DELETE /api/v1/categories/{id}           Soft delete (détache ses produits)
```

Un produit porte au plus une catégorie (`category_id`, nullable). En PATCH et en
synchro, `category_id` absent = inchangé, `null` = retiré ; une catégorie
inconnue de la boutique donne 422 (ADR-0008).

Images (produit, logo) : JPEG, PNG ou WebP, 5 Mo max (413 au-delà, 422 si ce
n'est pas une image). Ré-encodées en WebP sans métadonnées EXIF : 512 px max
pour un produit, 384 px de large pour le logo (imprimante 58 mm). Le binaire ne
passe jamais par la synchro : `image_version` / `logo_version` (SHA-256, null
sans image) servent de clé de cache, et changer d'image bumpe `updated_at`.

### Ventes

```
GET    /api/v1/sales                     Lister les ventes (paginé)
GET    /api/v1/sales/{id}                Détail d'une vente
GET    /api/v1/sales/today/summary       Résumé des ventes du jour
```

Note : pas de `POST /sales` direct. Les ventes sont créées uniquement via `/sync/sales` pour garantir l'idempotence.

### Synchronisation

```
POST   /api/v1/sync/sales                Push événements ventes (batch)
PUT    /api/v1/sync/categories           Push état catégorie (à envoyer avant les produits)
PUT    /api/v1/sync/products             Push état produit
GET    /api/v1/sync/changes              Pull des changements depuis un timestamp
```

`GET /sync/changes` renvoie les phases dans l'ordre catégories → produits →
ventes : une catégorie arrive toujours avant ses produits.

### Sessions de caisse

Une session de caisse suit les espèces d'un tiroir (un appareil) entre son ouverture et sa clôture (ADR-0015). Toutes les routes sont authentifiées et isolées par boutique (RLS) : une session d'une autre boutique donne 404. Les UUID des sessions et des mouvements sont générés par l'app.

| Route | Réponse | Statut |
|---|---|---|
| `POST /api/v1/cash-sessions` (ouvrir) | `CashSessionResponse` | 201 créée, 200 retry du même id |
| `GET /api/v1/cash-sessions/active?device_id=…` | `CashSessionDetailResponse` | 200, 404 si aucune session ouverte |
| `GET /api/v1/cash-sessions/{id}` | `CashSessionDetailResponse` | 200 |
| `GET /api/v1/cash-sessions?cursor=…&limit=…&device_id=…` (historique) | `CursorPage` de `CashSessionResponse` | 200 |
| `POST /api/v1/cash-sessions/{id}/movements` | `CashMovementResponse` | 201 créé, 200 retry du même id |
| `POST /api/v1/cash-sessions/{id}/close` | `CashSessionDetailResponse` | 200, y compris pour un retry identique |

Historique : `limit` de 1 à 100 (défaut 50), `device_id` optionnel, tri `opened_at` décroissant. La réponse est `{"items": CashSessionResponse[], "next_cursor": string | null, "has_more": bool}`. `next_cursor` est un jeton opaque : le renvoyer tel quel dans `?cursor=` pour la page suivante, sans le décoder.

**Montants** : chaînes décimales dans le JSON, dans les requêtes comme dans les réponses. Les montants stockés reviennent avec 2 décimales (`"25000"` envoyé revient `"25000.00"`) ; un total nul du résumé peut revenir `"0"`. Le client doit les parser en `Decimal` et ne jamais comparer les chaînes.

**Horodatages client** : `opened_at` (ouverture), `created_at` (mouvement) et `closed_at` (clôture) doivent porter un fuseau horaire et ne pas dépasser `now + 5 min` côté serveur (même règle que les ventes), sinon `VALIDATION_ERROR`.

**Retry (idempotence)** : un même UUID renvoyé avec le même contenu donne 200 et la ressource existante. Les champs comparés sont :

| Opération | Champs comparés | Différence |
|---|---|---|
| Ouverture | `device_id`, `opening_amount`, `opened_at` | `IDEMPOTENCY_CONFLICT` |
| Mouvement | `session_id` (de l'URL), `type`, `amount` | `IDEMPOTENCY_CONFLICT` ; un `reason` ou une `note` différents restent le même mouvement (200, valeurs d'origine) |
| Clôture | `counted_amount`, `closed_at` | `CASH_SESSION_CLOSED` |

Les montants sont comparés en valeur (`"3500"` et `"3500.00"` sont égaux). Pour la clôture, l'app **doit** persister le `closed_at` envoyé et renvoyer exactement la même valeur à chaque retry : un `closed_at` recalculé au moment du retry serait refusé.

Codes d'erreur propres au module :

| code | HTTP | sens |
|---|---|---|
| `CASH_SESSION_ALREADY_OPEN` | 409 | l'appareil a déjà une autre session ouverte |
| `CASH_SESSION_CLOSED` | 409 | mouvement postérieur à la clôture, ou clôture déjà enregistrée avec un autre `counted_amount` / `closed_at` |
| `INSUFFICIENT_CASH` | 422 | sortie supérieure au solde théorique |
| `IDEMPOTENCY_CONFLICT` | 409 | même UUID déjà utilisé avec un contenu différent |
| `NOT_FOUND` | 404 | session inconnue ou d'une autre boutique |
| `VALIDATION_ERROR` | 422 | payload invalide |

**Ouverture** (`POST /cash-sessions`) :

```json
{
  "id": "6f1c…",
  "device_id": "a2b9…",
  "opening_amount": "25000",
  "opening_note": "Fond de caisse lundi",
  "opened_at": "2026-11-10T07:58:12Z"
}
```

`opening_amount` ≥ 0 ; `opened_at` suit la règle des horodatages client ci-dessus. Une seule session ouverte par appareil, y compris face à deux requêtes concurrentes (index unique partiel).

**Mouvement** (`POST /cash-sessions/{id}/movements`) :

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

- `type` : `cash_in` (raisons `top_up`, `float`, `other`) ou `cash_out` (raisons `expense`, `withdrawal`, `supplies`, `other`). `amount` > 0. `note` obligatoire si `reason = other`.
- `created_at` suit la règle des horodatages client ci-dessus.
- La session est verrouillée (`FOR UPDATE`). Un retry qui attendait ce verrou pendant que la première requête insérait le même mouvement reçoit 200 et le mouvement existant, jamais `INSUFFICIENT_CASH`. Sur une session clôturée, un mouvement avec `created_at > closed_at` donne `CASH_SESSION_CLOSED` ; un mouvement antérieur à la clôture est accepté (sans contrôle de solde) et apparaît dans `late_impact`.
- Sur une session ouverte, une sortie supérieure au solde courant donne `INSUFFICIENT_CASH`.

**Clôture** (`POST /cash-sessions/{id}/close`) :

```json
{
  "counted_amount": "61000",
  "client_expected_amount": "61500",
  "closing_note": "Manque 500, monnaie rendue en trop",
  "closed_at": "2026-11-10T19:02:40Z"
}
```

- `closed_at` suit la règle des horodatages client ci-dessus ; l'app le persiste avant l'envoi pour pouvoir le renvoyer à l'identique en cas de retry.

- `counted_amount` ≥ 0. `client_expected_amount` est **obligatoire** et peut être **négatif** (les remboursements en espèces ne sont jamais bloqués, le solde peut passer sous zéro). Il sert uniquement à la traçabilité : le serveur recalcule `expected_amount` sous verrou et ne l'utilise jamais pour le calcul.
- `closing_note` est obligatoire seulement si `counted_amount ≠ expected_amount` (écart non nul), sinon `VALIDATION_ERROR` avec `field: closing_note`. `closed_at` ne peut pas précéder `opened_at`.
- Déjà clôturée avec les mêmes `counted_amount` et `closed_at` : 200 avec la clôture existante (idempotence). Valeurs différentes : `CASH_SESSION_CLOSED`. La réponse est un `CashSessionDetailResponse`.
- Une session clôturée n'est jamais rouverte ni modifiée (trigger PostgreSQL).

**Solde théorique** :

```
solde = opening_amount
      + Σ part espèces des ventes de la session
      + Σ entrées − Σ sorties
      − Σ refund_amount des retours en espèces de la session
```

La part espèces d'une vente vaut `total_amount` pour `cash`, `cash_amount` pour `mixed`, 0 pour le mobile money. Le rendu de monnaie n'entre pas en compte.

**Réponses** (la même session clôturée, après la clôture ci-dessus : 25000 + 48000 + 5000 − 14500 − 2000 = 61500 attendus, 61000 comptés) :

```json
// CashSessionResponse
{
  "id": "6f1c…", "device_id": "a2b9…", "status": "closed",
  "opening_amount": "25000.00", "opening_note": "Fond de caisse lundi",
  "opened_at": "2026-11-10T07:58:12Z", "opened_by": "…",
  "expected_amount": "61500.00", "client_expected_amount": "61500.00",
  "counted_amount": "61000.00", "discrepancy_amount": "-500.00",
  "closing_note": "Manque 500, monnaie rendue en trop",
  "closed_at": "2026-11-10T19:02:40Z", "closed_by": "…"
}

// CashMovementResponse
{
  "id": "0d4e…", "session_id": "6f1c…", "type": "cash_out", "reason": "supplies",
  "amount": "3500.00", "note": "Sachets", "created_at": "2026-11-10T11:20:00Z",
  "created_by": "…", "synced_at": "2026-11-10T11:20:05Z"
}

// CashSessionDetailResponse
{
  "session": { /* CashSessionResponse ci-dessus */ },
  "summary": {
    "opening_amount": "25000.00",
    "cash_sales": "48000.00", "cash_sales_count": 23,
    "mobile_money_sales": "31000.00",
    "cash_in": "5000.00", "cash_out": "14500.00",
    "cash_refunds": "2000.00",
    "expected_amount": "61500.00",
    "late_impact": "0.00",
    "server_recalculated": false
  },
  "movements": [ /* CashMovementResponse, du plus récent au plus ancien */ ]
}
```

- Session ouverte : `summary.expected_amount` est le solde courant, `late_impact` vaut 0 et `server_recalculated` vaut toujours `false`. `session.expected_amount`, `client_expected_amount`, `counted_amount`, `discrepancy_amount`, `closed_at` et `closed_by` sont `null`.
- Session clôturée : `summary.expected_amount` est le montant figé (égal à `session.expected_amount`), `discrepancy_amount` = `counted_amount` − `expected_amount`, et `late_impact` = recalcul actuel − montant figé (opérations arrivées après la clôture).
- `server_recalculated` vaut `true` si le montant figé diffère de `client_expected_amount` (l'app affichait un autre solde ; par exemple `client_expected_amount = "62000"` ci-dessus aurait donné `true`).
- `cash_sales_count` compte les ventes qui ont une part espèces (`cash` et `mixed`). `mobile_money_sales` est informatif et n'entre jamais dans le solde.
- `closed_by` et `opened_by` sont nullables (FK `SET NULL` si l'utilisateur est supprimé).

**Synchronisation** : `SaleCreate` et `SaleReturnCreate` acceptent un champ optionnel `cash_session_id` (absent = hors session, anciennes versions de l'app). `SaleResponse` et `SaleReturnResponse` l'exposent, donc `GET /sync/changes` le transmet sans nouvelle phase.

- Création directe (`POST /api/v1/sales`) avec un `cash_session_id` inconnu ou d'une autre boutique : 404 `NOT_FOUND` avec `field: cash_session_id`, rien n'est écrit.
- Sync : session inconnue du serveur (ou d'une autre boutique) : l'opération sort en `failed` avec l'erreur `cash session not found`. Elle est réessayable (l'ouverture n'est peut-être pas encore arrivée) et n'est **jamais** `rejected`.
- Session clôturée : vente et retour sont toujours acceptés et rattachés à leur session. Ils ne modifient pas `expected_amount` figé et apparaissent dans `late_impact`.
- Le serveur ne réattribue jamais une opération : il garde la session envoyée par l'app.

### Administration plateforme

Réservé à l'administrateur de la plateforme (jeton distinct, `aud = "pos-admin"`, 120 min, pas de refresh, ADR-0012). 403 si `ADMIN_JWT_SECRET` n'est pas configuré. Les jetons commerçant sont refusés.

```
POST   /api/v1/admin/auth/login                 Connexion admin (email, mot de passe) ; 5 échecs = blocage 15 min
GET    /api/v1/admin/metrics                    Indicateurs plateforme
GET    /api/v1/admin/metrics/daily              Activité par jour, Africa/Abidjan (days 7-90, défaut 30)
GET    /api/v1/admin/stores                     Liste des boutiques (search nom/téléphone/email, status=all|active|suspended, inactive, sort=last_sale|created, limit 1-100, offset)
GET    /api/v1/admin/stores/{id}                Fiche boutique : propriétaire, produits, ventes 30 j, 20 dernières actions admin
POST   /api/v1/admin/stores/{id}/suspend        Suspendre une boutique (body {reason?})
POST   /api/v1/admin/stores/{id}/reactivate     Réactiver une boutique
GET    /api/v1/admin/users                      Comptes commerçants (search téléphone/email/nom, store=all|with|without, limit 1-100, offset)
GET    /api/v1/admin/audit-log                  Journal des actions admin (store_id?, limit 1-100, offset)
```

### Système

```
GET    /health                           Health check (pas de /api/v1)
GET    /                                 Bienvenue + version
```

`/health` renvoie `{"status": "ok", "version": "…", "min_app_build": 0}`. `min_app_build` vient de la variable `MIN_APP_BUILD` (versionCode Android, 0 par défaut = aucun blocage) : l'app mobile dont le numéro de build est inférieur affiche un dialogue de mise à jour obligatoire. Ne la relever qu'**après** la publication du build correspondant sur le Play Store.

## Rate limiting

Implémenté dans `app/core/rate_limit.py` (fenêtre glissante, en mémoire) et appliqué dans `app/modules/auth/router.py`.

| Endpoint | Par compte | Par IP |
|---|---|---|
| `POST /auth/login` | 5 échecs / 15 min par (numéro, IP), 50 échecs / 15 min par numéro | 30 / min |
| `POST /auth/forgot-password` | 3 / h par email | 10 / h |
| `POST /auth/register` | — | 10 / h |
| `POST /auth/reset-password` | — | 10 / h |

Sur le login, seuls les échecs comptent et un succès remet les compteurs à zéro : une IP apporte au plus 5 échecs au compteur du numéro, donc bloquer un compte demande au moins 10 IP distinctes. Les limites strictes portent sur le compte visé : les opérateurs mobiles partagent souvent une IP entre de nombreux abonnés (CGNAT). Pas de limite sur les endpoints authentifiés. Le login admin a son propre verrouillage en base (5 échecs → 15 min).

En cas de dépassement, le serveur renvoie `429` au format d'erreur habituel (`code: "RATE_LIMITED"`) avec un header `Retry-After` indiquant le nombre de secondes à attendre.

L'IP client est lue dans l'en-tête `CLIENT_IP_HEADER` s'il est défini. Sur Render, toujours derrière Cloudflare, utiliser `cf-connecting-ip`, que Cloudflare écrase. `X-Forwarded-For` y vaut `<client>, <edge Cloudflare>` et le client peut y ajouter des entrées à gauche. Sans `CLIENT_IP_HEADER`, on lit `X-Forwarded-For` à `TRUSTED_PROXY_COUNT` crans de la droite. Constaté en prod le 2026-11-04 : avec `TRUSTED_PROXY_COUNT=1`, la clé était l'IP de l'edge Cloudflare (compteur partagé entre utilisateurs).

**Limite connue** : les compteurs vivent dans le process. Ils repartent à zéro à chaque redéploiement et ne sont pas partagés entre instances : passer à un stockage partagé avant de lancer plusieurs workers ou instances.

## Génération du client Flutter depuis OpenAPI

Le client HTTP côté Flutter est généré automatiquement depuis le schéma OpenAPI exposé par FastAPI. Cela évite de dupliquer manuellement les modèles entre backend et mobile.

```bash
# Côté mobile
flutter pub run openapi_generator
```

La configuration est dans `mobile/openapi-generator.yaml`. Le client est régénéré à chaque changement significatif de l'API.

## Versioning et compatibilité

Pendant le MVP, l'API évolue rapidement. **Chaque déploiement peut casser la compatibilité avec les anciennes versions de l'app Flutter en bêta.** Cette tolérance disparaît après le passage en GA.

Conventions :

- Une minor version Flutter (ex: 1.2.0 → 1.3.0) peut nécessiter un déploiement backend
- Les changements cassants côté API impliquent une migration côté Flutter à pousser via Play Store
- Pour les changements non cassants (nouveau champ optionnel par exemple), pas de problème

## Outils de test manuel

### Avec curl

```bash
# Login
curl -X POST https://api.pos-mobile-ci.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPassword123"}'

# Lister les produits avec un token
curl https://api.pos-mobile-ci.com/api/v1/products \
  -H "Authorization: Bearer <TOKEN>"
```

### Avec httpie (plus lisible)

```bash
http POST https://api.pos-mobile-ci.com/api/v1/auth/login \
  email=test@example.com password=TestPassword123

http GET https://api.pos-mobile-ci.com/api/v1/products \
  Authorization:"Bearer <TOKEN>"
```

### Avec Insomnia / Bruno

Une collection Bruno est fournie dans `tools/bruno/` avec tous les endpoints pré-configurés et les variables d'environnement (local, staging, prod).
