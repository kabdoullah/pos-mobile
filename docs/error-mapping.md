# Backend Error Messages Mapping

All backend errors follow this response format:

```json
{
  "detail": "Error message (always in English)",
  "code": "ERROR_CODE",
  "field": "field_name_or_null"
}
```

Map these `code` + `detail` combinations to French UI messages on the frontend.

## Exception Types & HTTP Status Codes

| Code | HTTP | Description |
|------|------|-------------|
| `NOT_FOUND` | 404 | Resource does not exist |
| `UNAUTHORIZED` | 401 | JWT missing, invalid, or expired |
| `FORBIDDEN` | 403 | User lacks permission |
| `CONFLICT` | 409 | Conflict during upsert/sync (duplicate or state mismatch) |
| `VALIDATION_ERROR` | 422 | Business logic validation failed (not Pydantic) |
| `APP_ERROR` | 400 | Generic error (rare) |

---

## All Error Messages by Module

### Auth Module (`/api/v1/auth/*`)

#### Register (`POST /api/v1/auth/register`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `This email is already registered.` | `CONFLICT` | `email` | User tried to register with existing email |

#### Login (`POST /api/v1/auth/login`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Invalid email or password.` | `UNAUTHORIZED` | — | Email not found OR password wrong. Intentionally vague. |
| `Account is disabled.` | `UNAUTHORIZED` | — | User account `is_active = false` |

#### Refresh Token (`POST /api/v1/auth/refresh`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Invalid or expired refresh token.` | `UNAUTHORIZED` | — | Refresh token missing, malformed, or past expiry |
| `User not found or disabled.` | `UNAUTHORIZED` | — | User deleted or deactivated after token creation |

#### Reset Password (`POST /api/v1/auth/reset-password`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Invalid or expired token.` | `VALIDATION_ERROR` | — | Reset token missing, malformed, expired, or already used |

---

### Catalog Module (`/api/v1/products/*`)

#### Get Product (`GET /api/v1/products/{product_id}`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Product not found.` | `NOT_FOUND` | — | Product ID does not exist OR is soft-deleted |

#### Get by Barcode (`GET /api/v1/products/barcode/{barcode}`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Product not found.` | `NOT_FOUND` | — | Barcode does not exist OR product is soft-deleted |

#### Create Product (`POST /api/v1/products`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `A product with this barcode already exists.` | `CONFLICT` | `barcode` | Barcode uniqueness violation (within store) |

#### Update Product (`PATCH /api/v1/products/{product_id}`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Product not found.` | `NOT_FOUND` | — | Product ID does not exist OR is soft-deleted |
| `A product with this barcode already exists.` | `CONFLICT` | `barcode` | New barcode conflicts with existing product |

#### Delete Product (`DELETE /api/v1/products/{product_id}`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Product not found.` | `NOT_FOUND` | — | Product ID does not exist OR already soft-deleted |

---

### Sales Module (`/api/v1/sales/*`)

#### Get Sale (`GET /api/v1/sales/{sale_id}`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Sale not found.` | `NOT_FOUND` | — | Sale ID does not exist |

#### Create Sale (`POST /api/v1/sales`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Product not found.` | `NOT_FOUND` | — | One or more sale items reference missing products |

---

### Stores Module (`/api/v1/stores*`)

#### Get Store (`GET /api/v1/stores`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Store not found.` | `NOT_FOUND` | — | User has no store (shouldn't happen post-registration) |

#### Create Store (`POST /api/v1/stores`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `A store already exists for this user.` | `CONFLICT` | `owner_id` | User can only have one store |

#### Update Store (`PATCH /api/v1/stores`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `Store not found.` | `NOT_FOUND` | — | User has no store |

---

### Sync Module (`/api/v1/sync/*`)

#### Sync Changes (`GET /api/v1/sync/changes`)

| Error | Code | Field | Notes |
|-------|------|-------|-------|
| `since must be timezone-aware` | `VALIDATION_ERROR` | — | `since` query param is not a valid timezone-aware ISO datetime |

---

## Pydantic Validation Errors (422)

When request body/query params fail Pydantic validation, FastAPI returns a `422 Unprocessable Entity` with this structure:

```json
{
  "detail": [
    {
      "type": "string_type",
      "loc": ["body", "email"],
      "msg": "Input should be a valid string",
      "input": 123
    }
  ]
}
```

**Common Pydantic errors:**
- `string_type` — field expected string
- `string_too_short` — string length < min_length
- `email_invalid` — invalid email format
- `int_parsing` — int conversion failed
- `missing` — required field missing

**Frontend mapping:** Provide generic UI messages for all Pydantic errors (form validation feedback), e.g.:
- "Invalid input format"
- "Field is required"
- "Invalid email address"

---

## Authentication Errors

**Missing JWT:** No `Authorization: Bearer <token>` header on protected endpoints

```json
{
  "detail": "Not authenticated",
  "code": "UNAUTHORIZED",
  "field": null
}
```

**Expired/Invalid JWT:** Malformed or past-expiry token

```json
{
  "detail": "Invalid credentials",
  "code": "UNAUTHORIZED",
  "field": null
}
```

---

## Summary for i18n Keys

Suggested French mapping structure:

```json
{
  "errors": {
    "conflict": {
      "email_already_registered": "Cet email est déjà enregistré",
      "store_exists": "Une boutique existe déjà pour cet utilisateur",
      "barcode_duplicate": "Un produit avec ce code-barres existe déjà"
    },
    "unauthorized": {
      "invalid_credentials": "Email ou mot de passe incorrect",
      "account_disabled": "Le compte est désactivé",
      "invalid_refresh_token": "Le token de rafraîchissement est invalide ou expiré",
      "user_not_found_disabled": "Utilisateur introuvable ou désactivé"
    },
    "not_found": {
      "product_not_found": "Produit introuvable",
      "sale_not_found": "Vente introuvable",
      "store_not_found": "Boutique introuvable"
    },
    "validation": {
      "invalid_token": "Le token est invalide ou expiré",
      "since_must_be_timezone_aware": "La date 'since' doit être au format ISO avec fuseau horaire"
    }
  }
}
```

