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

### Boutique

```
GET    /api/v1/stores                     Récupérer ma boutique
PATCH  /api/v1/stores                     Mettre à jour ma boutique
```

### Catalogue

```
GET    /api/v1/products                  Lister les produits (paginé)
POST   /api/v1/products                  Créer un produit
GET    /api/v1/products/{id}             Récupérer un produit
PATCH  /api/v1/products/{id}             Mettre à jour un produit
DELETE /api/v1/products/{id}             Soft delete un produit
GET    /api/v1/products/by-barcode/{ean} Recherche par code-barres
```

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
PUT    /api/v1/sync/products             Push état produit
GET    /api/v1/sync/changes              Pull des changements depuis un timestamp
```

### Système

```
GET    /health                           Health check (pas de /api/v1)
GET    /                                 Bienvenue + version
```

## Rate limiting

| Endpoint | Limite |
|---|---|
| `/auth/login` | 5 tentatives par minute par IP |
| `/auth/forgot-password` | 3 par heure par IP |
| Autres endpoints authentifiés | 100 par minute par utilisateur |

En cas de dépassement, le serveur renvoie `429 Too Many Requests` avec un header `Retry-After` indiquant le nombre de secondes à attendre.

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
