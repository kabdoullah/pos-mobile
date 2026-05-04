# Modèle de données détaillé

> Document de référence DDL. Dernière mise à jour : 29 avril 2026 — version 1.0.

Ce document contient le DDL complet de la base PostgreSQL du backend POS Mobile CI, avec justification des choix de typage, des contraintes, et des politiques RLS.

Pour la vue d'ensemble et les conventions, voir [data-model.md](data-model.md).
Pour l'architecture multi-tenant, voir [adr/0002-multi-tenancy-rls.md](adr/0002-multi-tenancy-rls.md).

## Sommaire

1. [Préambule : extensions et fonctions utilitaires](#préambule)
2. [Tables hors-tenant : users, tokens](#tables-hors-tenant)
3. [Table racine : stores](#table-racine-stores)
4. [Tables tenant : products, sales, sale_items](#tables-tenant)
5. [Politiques Row-Level Security](#politiques-row-level-security)
6. [Triggers automatiques](#triggers-automatiques)
7. [Index de performance](#index-de-performance)
8. [Décisions structurantes](#décisions-structurantes)

## Préambule

### Extensions PostgreSQL utilisées

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
-- Fournit gen_random_uuid() pour générer des UUID v4 côté serveur en fallback
-- (les UUID sont normalement générés côté client pour l'idempotence sync)

CREATE EXTENSION IF NOT EXISTS "pg_trgm";
-- Trigram matching pour la recherche full-text par nom de produit
-- (utilisé en Phase 2, optionnel au MVP mais peu coûteux à activer)
```

### Fonction utilitaire : updated_at automatique

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';
```

Cette fonction est appelée par les triggers de chaque table tenant (sauf `sales` qui est immuable).

### Type ENUM pour les modes de paiement

```sql
CREATE TYPE payment_method_enum AS ENUM (
    'cash',
    'mobile_money_orange',
    'mobile_money_mtn',
    'mobile_money_wave',
    'mixed'
);
```

Pourquoi ENUM plutôt que VARCHAR + CHECK :
- Performance légèrement meilleure (4 bytes vs varchar)
- Documentation auto-portante (le type définit les valeurs valides)
- Erreur immédiate si on tente d'insérer une valeur invalide
- Inconvénient : ajouter une valeur nécessite `ALTER TYPE` (mais c'est rare)

## Tables hors-tenant

Ces tables ne sont pas soumises au RLS car elles ne contiennent pas de données métier d'un tenant donné.

### Table `users`

Comptes globaux. Un utilisateur possède exactement une boutique au MVP.

```sql
CREATE TABLE users (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255)    NOT NULL,
    password_hash   VARCHAR(255)    NOT NULL,
    phone_number    VARCHAR(20)     NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    email_verified_at TIMESTAMPTZ   NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT chk_users_email_lowercase CHECK (email = LOWER(email)),
    CONSTRAINT chk_users_email_format
        CHECK (email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$')
);

CREATE INDEX idx_users_email ON users (email);
COMMENT ON COLUMN users.password_hash IS 'bcrypt hash, cost factor 12';
COMMENT ON COLUMN users.email_verified_at IS 'NULL = email pas encore confirmé via lien email';
```

**Choix de typage justifiés** :

- `email VARCHAR(255)` : la RFC 5321 limite techniquement à 254 caractères, on prend 255 pour la marge.
- `password_hash VARCHAR(255)` : un hash bcrypt fait exactement 60 caractères, mais on prévoit large pour permettre une migration future vers argon2 ou scrypt sans changer le schéma.
- `phone_number VARCHAR(20)` : format international `+225 XX XX XX XX XX` = 18 caractères avec espaces. On stocke avec ou sans espaces selon préférence (à normaliser côté code).
- Pas de soft delete : les utilisateurs sont supprimés en hard delete avec restriction (voir [Décisions structurantes](#décisions-structurantes)).

### Table `email_verification_tokens`

```sql
CREATE TABLE email_verification_tokens (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL,
    token_hash      VARCHAR(255)    NOT NULL,
    expires_at      TIMESTAMPTZ     NOT NULL,
    used_at         TIMESTAMPTZ     NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_email_verification_tokens_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_email_verification_tokens_hash UNIQUE (token_hash)
);

CREATE INDEX idx_email_verification_tokens_user_id ON email_verification_tokens (user_id);
CREATE INDEX idx_email_verification_tokens_expires_at ON email_verification_tokens (expires_at);

COMMENT ON COLUMN email_verification_tokens.token_hash IS 'Hash du token, le clair est envoyé par email';
COMMENT ON COLUMN email_verification_tokens.used_at IS 'NULL = token pas encore utilisé. Token à usage unique.';
```

### Table `password_reset_tokens`

Structure identique à `email_verification_tokens` :

```sql
CREATE TABLE password_reset_tokens (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL,
    token_hash      VARCHAR(255)    NOT NULL,
    expires_at      TIMESTAMPTZ     NOT NULL,
    used_at         TIMESTAMPTZ     NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_password_reset_tokens_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_password_reset_tokens_hash UNIQUE (token_hash)
);

CREATE INDEX idx_password_reset_tokens_user_id ON password_reset_tokens (user_id);
CREATE INDEX idx_password_reset_tokens_expires_at ON password_reset_tokens (expires_at);
```

**Note** : ces deux tables sont structurellement identiques. On garde des tables séparées plutôt qu'une table `tokens` avec un champ `type` parce que :
- Plus clair sémantiquement
- Permet de purger les tokens expirés indépendamment
- Pas de surcoût significatif

## Table racine `stores`

C'est la table pivot du multi-tenancy. Toutes les autres tables tenant référencent `stores.id` via leur colonne `store_id`.

```sql
CREATE TABLE stores (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id                UUID            NOT NULL,
    name                    VARCHAR(255)    NOT NULL,
    address                 TEXT            NULL,
    ncc                     VARCHAR(20)     NULL,
    vat_subject             BOOLEAN         NOT NULL DEFAULT FALSE,
    receipt_footer_text     VARCHAR(200)    NULL,
    next_receipt_number     INTEGER         NOT NULL DEFAULT 1,
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_stores_owner
        FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT uq_stores_owner UNIQUE (owner_id),
    CONSTRAINT chk_stores_ncc_format
        CHECK (ncc IS NULL OR (length(ncc) BETWEEN 7 AND 13)),
    CONSTRAINT chk_stores_next_receipt_number
        CHECK (next_receipt_number >= 1)
);

CREATE INDEX idx_stores_owner_id ON stores (owner_id);

COMMENT ON COLUMN stores.owner_id IS '1 boutique par utilisateur au MVP (contrainte UNIQUE)';
COMMENT ON COLUMN stores.ncc IS 'Numéro de Compte Contribuable DGI, optionnel pour les non-immatriculés';
COMMENT ON COLUMN stores.vat_subject IS 'TRUE = la boutique facture la TVA à 18%';
COMMENT ON COLUMN stores.next_receipt_number IS 'Compteur du prochain numéro de reçu pour cette boutique';
```

**Détails importants** :

- `next_receipt_number` est sur la table `stores` plutôt que dans une table `sequences` séparée. C'est un choix de simplicité — pour 1 vente par seconde max, le row-level locking PostgreSQL sur la mise à jour de ce compteur lors de la création d'une vente est suffisant.
- `ON DELETE RESTRICT` sur `owner_id` empêche de supprimer un user qui a une boutique. La suppression nécessite d'abord d'anonymiser/supprimer la boutique et tout son contenu.
- Pas de colonne `is_active` ou `deleted_at` sur stores : la suppression est définitive (voir [Décisions structurantes](#décisions-structurantes)).

## Tables tenant

Ces tables sont soumises aux politiques RLS. Toutes ont une colonne `store_id NOT NULL` indexée.

### Table `products`

Catalogue produits d'une boutique.

```sql
CREATE TABLE products (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id        UUID            NOT NULL,
    name            VARCHAR(255)    NOT NULL,
    barcode         VARCHAR(50)     NULL,
    unit_price      NUMERIC(12, 2)  NOT NULL,
    current_stock   INTEGER         NULL,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ     NULL,

    CONSTRAINT fk_products_store
        FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT,
    CONSTRAINT chk_products_unit_price_positive
        CHECK (unit_price >= 0),
    CONSTRAINT chk_products_current_stock_non_negative
        CHECK (current_stock IS NULL OR current_stock >= 0),
    CONSTRAINT chk_products_name_not_empty
        CHECK (length(trim(name)) > 0)
);

-- Index composite pour la recherche dans une boutique
CREATE INDEX idx_products_store_name ON products (store_id, name)
    WHERE deleted_at IS NULL;

-- Index composite pour le scan code-barres
CREATE INDEX idx_products_store_barcode ON products (store_id, barcode)
    WHERE barcode IS NOT NULL AND deleted_at IS NULL;

-- Contrainte unique partielle : un code-barres ne peut être présent qu'une fois
-- par boutique parmi les produits non supprimés
CREATE UNIQUE INDEX uq_products_store_barcode_active
    ON products (store_id, barcode)
    WHERE barcode IS NOT NULL AND deleted_at IS NULL;

COMMENT ON COLUMN products.current_stock IS 'NULL = stock non géré pour ce produit';
COMMENT ON COLUMN products.unit_price IS 'Prix en FCFA. Stocké en NUMERIC pour préserver précision et anticiper multi-devises.';
COMMENT ON COLUMN products.deleted_at IS 'Soft delete : NULL = actif, NOT NULL = supprimé';
```

**Pourquoi un soft delete sur `products` mais pas sur `stores`** :

Les ventes passées (`sale_items`) référencent les produits via `product_id`. Si on hard-delete un produit, les ventes perdent la référence. Le soft delete préserve l'intégrité de l'historique tout en cachant le produit dans les listings actifs.

À l'inverse, les `stores` ne sont pas référencées par autre chose qu'à travers le RLS, donc un hard delete avec RESTRICT est suffisant.

### Table `sales` (immuable)

Vente encaissée. **Aucun UPDATE ni DELETE n'est autorisé sur cette table après insertion.**

```sql
CREATE TABLE sales (
    id                      UUID            PRIMARY KEY,  -- pas de DEFAULT : généré côté client
    store_id                UUID            NOT NULL,
    receipt_number          INTEGER         NOT NULL,
    total_amount            NUMERIC(12, 2)  NOT NULL,
    vat_amount              NUMERIC(12, 2)  NOT NULL DEFAULT 0,
    payment_method          payment_method_enum NOT NULL,
    cash_amount             NUMERIC(12, 2)  NULL,
    mobile_money_amount     NUMERIC(12, 2)  NULL,
    created_at              TIMESTAMPTZ     NOT NULL,  -- pas de DEFAULT : timestamp client
    synced_at               TIMESTAMPTZ     NOT NULL DEFAULT now(),

    CONSTRAINT fk_sales_store
        FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT,
    CONSTRAINT uq_sales_store_receipt_number
        UNIQUE (store_id, receipt_number),
    CONSTRAINT chk_sales_amounts_positive
        CHECK (total_amount >= 0 AND vat_amount >= 0),
    CONSTRAINT chk_sales_vat_lte_total
        CHECK (vat_amount <= total_amount),
    CONSTRAINT chk_sales_mixed_amounts
        CHECK (
            (payment_method = 'mixed' AND cash_amount IS NOT NULL AND mobile_money_amount IS NOT NULL)
            OR (payment_method != 'mixed' AND (cash_amount IS NULL OR mobile_money_amount IS NULL))
        ),
    CONSTRAINT chk_sales_mixed_sum_equals_total
        CHECK (
            payment_method != 'mixed'
            OR (COALESCE(cash_amount, 0) + COALESCE(mobile_money_amount, 0) = total_amount)
        ),
    CONSTRAINT chk_sales_receipt_number_positive
        CHECK (receipt_number >= 1)
);

CREATE INDEX idx_sales_store_created_at ON sales (store_id, created_at DESC);
CREATE INDEX idx_sales_store_receipt_number ON sales (store_id, receipt_number);

COMMENT ON TABLE sales IS 'Table immuable. Aucun UPDATE/DELETE autorisé après insertion.';
COMMENT ON COLUMN sales.id IS 'UUID v4 généré côté client pour idempotence sync (INSERT ON CONFLICT DO NOTHING).';
COMMENT ON COLUMN sales.receipt_number IS 'Numéro séquentiel par boutique (généré côté serveur au sync, voir doc).';
COMMENT ON COLUMN sales.created_at IS 'Timestamp de la vente côté client (pas le timestamp serveur).';
COMMENT ON COLUMN sales.synced_at IS 'Timestamp de réception serveur. Sert au pull /sync/changes?since=...';
```

**Notes critiques** :

- `id UUID PRIMARY KEY` sans `DEFAULT` : volontaire. Le client génère son UUID, le serveur ne doit pas en créer un de fallback (sinon perte d'idempotence).
- `created_at TIMESTAMPTZ NOT NULL` sans `DEFAULT` : c'est l'heure côté client au moment de la vente, pas l'heure serveur. Important pour les ventes offline qui sont synchronisées plusieurs heures plus tard.
- `synced_at` : sert d'horloge serveur fiable pour le pull `/sync/changes?since=...`. Voir [adr/0003-sync-hybride.md](adr/0003-sync-hybride.md).
- Aucun trigger `updated_at` : la table est immuable.

### Table `sale_items`

Lignes individuelles d'une vente. Une vente a 1 à N lignes.

```sql
CREATE TABLE sale_items (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    sale_id                 UUID            NOT NULL,
    store_id                UUID            NOT NULL,  -- dénormalisé pour le RLS
    product_id              UUID            NULL,      -- nullable pour les produits supprimés
    product_name_at_sale    VARCHAR(255)    NOT NULL,
    unit_price_at_sale      NUMERIC(12, 2)  NOT NULL,
    quantity                INTEGER         NOT NULL,
    line_total              NUMERIC(12, 2)  NOT NULL,

    CONSTRAINT fk_sale_items_sale
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    CONSTRAINT fk_sale_items_store
        FOREIGN KEY (store_id) REFERENCES stores(id) ON DELETE RESTRICT,
    CONSTRAINT fk_sale_items_product
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
    CONSTRAINT chk_sale_items_quantity_positive
        CHECK (quantity > 0),
    CONSTRAINT chk_sale_items_unit_price_positive
        CHECK (unit_price_at_sale >= 0),
    CONSTRAINT chk_sale_items_line_total
        CHECK (line_total = unit_price_at_sale * quantity)
);

CREATE INDEX idx_sale_items_sale_id ON sale_items (sale_id);
CREATE INDEX idx_sale_items_store_id ON sale_items (store_id);
CREATE INDEX idx_sale_items_product_id ON sale_items (product_id) WHERE product_id IS NOT NULL;

COMMENT ON COLUMN sale_items.product_id IS 'NULL si le produit a été hard-deleted (rare). Le nom et le prix sont copiés dans product_name_at_sale et unit_price_at_sale pour préserver l''historique.';
COMMENT ON COLUMN sale_items.store_id IS 'Dénormalisé depuis sales.store_id pour le RLS (évite une jointure systématique).';
COMMENT ON COLUMN sale_items.product_name_at_sale IS 'Copie du nom au moment de la vente (immuabilité).';
COMMENT ON COLUMN sale_items.unit_price_at_sale IS 'Copie du prix au moment de la vente (immuabilité).';
```

**Pourquoi `store_id` est dénormalisé sur `sale_items`** :

Sans cette dénormalisation, le RLS sur `sale_items` devrait faire `WHERE sale_id IN (SELECT id FROM sales WHERE store_id = ...)`. C'est :
- Plus lent (sous-requête à chaque check)
- Plus complexe à exprimer en politique RLS
- Risqué si quelqu'un fait un `SELECT * FROM sale_items` sans jointure

Avoir `store_id` directement permet une politique RLS triviale et performante.

**Le coût** : on doit s'assurer que `store_id` reste cohérent avec celui de la `sales` parente. C'est garanti par le code applicatif (le service ne permet pas d'insérer un `sale_item` avec un `store_id` différent de la `sale`). On pourrait ajouter un trigger BEFORE INSERT qui le vérifie, mais c'est de la défense en profondeur optionnelle.

## Politiques Row-Level Security

Activation et politiques pour chaque table tenant :

```sql
-- ============================================================
-- products
-- ============================================================
ALTER TABLE products ENABLE ROW LEVEL SECURITY;

CREATE POLICY rls_products_tenant_isolation ON products
    USING (store_id = current_setting('app.current_store_id', true)::uuid)
    WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);

-- ============================================================
-- sales
-- ============================================================
ALTER TABLE sales ENABLE ROW LEVEL SECURITY;

CREATE POLICY rls_sales_tenant_isolation ON sales
    USING (store_id = current_setting('app.current_store_id', true)::uuid)
    WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);

-- ============================================================
-- sale_items
-- ============================================================
ALTER TABLE sale_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY rls_sale_items_tenant_isolation ON sale_items
    USING (store_id = current_setting('app.current_store_id', true)::uuid)
    WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);

-- ============================================================
-- stores (cas particulier)
-- ============================================================
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;

CREATE POLICY rls_stores_self_access ON stores
    USING (id = current_setting('app.current_store_id', true)::uuid)
    WITH CHECK (id = current_setting('app.current_store_id', true)::uuid);
```

**Pourquoi `current_setting('app.current_store_id', true)::uuid`** :

- Le 2e argument `true` (`missing_ok`) : retourne NULL si le setting n'est pas défini, plutôt qu'une erreur. Permet aux endpoints d'auth (qui n'ont pas encore de `store_id`) de fonctionner.
- `::uuid` : cast explicite vers UUID pour la comparaison.
- Quand le setting n'est pas défini, NULL ne matchera aucune ligne, donc isolation préservée par défaut.

**Politique pour `stores`** : `USING id = ...` au lieu de `store_id = ...` car la table elle-même EST la boutique.

**Pas de politique RLS sur `users`, `email_verification_tokens`, `password_reset_tokens`** : ces tables ne sont pas tenant-scoped. Leur sécurité repose uniquement sur le code applicatif (filtre par `user_id` extrait du JWT).

### Tester le RLS (à faire systématiquement)

Test critique à écrire dès la première migration :

```python
async def test_user_a_cannot_read_products_of_user_b(client_a, client_b, db_session):
    # Créer 2 stores avec leurs produits
    product_b = await create_product(client_b, name="Pain de B")

    # User A tente de lire le produit de B directement
    response = await client_a.get(f"/api/v1/products/{product_b.id}")

    # Doit renvoyer 404 (et pas 200 ni 403) car le RLS a filtré la ligne
    assert response.status_code == 404
```

Ce test doit passer à chaque ajout de table tenant.

## Triggers automatiques

### Triggers `updated_at`

Tables concernées : `users`, `stores`, `products`. Pas sur `sales` (immuable) ni sur les tokens (créés une fois, jamais modifiés sauf `used_at`).

```sql
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_stores_updated_at
    BEFORE UPDATE ON stores
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_products_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### Trigger d'immuabilité sur `sales`

Empêche tout UPDATE ou DELETE sur la table `sales`, défense en profondeur en plus du code applicatif :

```sql
CREATE OR REPLACE FUNCTION prevent_sales_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'sales table is immutable: % not allowed', TG_OP
        USING ERRCODE = 'feature_not_supported';
END;
$$ language 'plpgsql';

CREATE TRIGGER trg_sales_immutable_update
    BEFORE UPDATE ON sales
    FOR EACH ROW
    EXECUTE FUNCTION prevent_sales_modification();

CREATE TRIGGER trg_sales_immutable_delete
    BEFORE DELETE ON sales
    FOR EACH ROW
    EXECUTE FUNCTION prevent_sales_modification();
```

**Pourquoi cette double protection** : si un bug dans le code applicatif tente d'UPDATE une vente, le trigger échoue avant que la modification soit appliquée. Coût négligeable, robustesse maximale.

Note : `sale_items` n'a pas ce trigger car le ON DELETE CASCADE depuis `sales` doit pouvoir fonctionner si on devait un jour faire une opération admin (test, RGPD). Mais en pratique, le trigger `prevent_sales_modification` rend la cascade impossible.

### Trigger de génération du `receipt_number`

Le numéro de reçu est généré atomiquement côté serveur lors de l'INSERT dans `sales`, en lisant et incrémentant `stores.next_receipt_number` :

```sql
CREATE OR REPLACE FUNCTION generate_receipt_number()
RETURNS TRIGGER AS $$
BEGIN
    -- Si le client envoie déjà un receipt_number, on le respecte (cas rare, edge case)
    IF NEW.receipt_number IS NOT NULL AND NEW.receipt_number > 0 THEN
        RETURN NEW;
    END IF;

    -- Sinon, lock la ligne stores correspondante et lit/incrémente le compteur
    UPDATE stores
    SET next_receipt_number = next_receipt_number + 1
    WHERE id = NEW.store_id
    RETURNING next_receipt_number - 1 INTO NEW.receipt_number;

    IF NEW.receipt_number IS NULL THEN
        RAISE EXCEPTION 'Could not generate receipt_number for store_id %', NEW.store_id;
    END IF;

    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER trg_sales_receipt_number
    BEFORE INSERT ON sales
    FOR EACH ROW
    EXECUTE FUNCTION generate_receipt_number();
```

**Pourquoi un trigger plutôt que du code applicatif** :

- Atomique : l'UPDATE de `stores.next_receipt_number` et l'INSERT de `sales` sont dans la même transaction. Pas de course possible entre 2 ventes simultanées.
- Centralisé : tous les inserts passent par là, impossible d'oublier la logique de génération.
- Performant : un seul aller-retour SQL au lieu de SELECT + UPDATE + INSERT.

**Limite connue** : la table `stores` voit son `next_receipt_number` mis à jour à chaque vente. Ça peut créer du contention si le commerçant fait 100 ventes par seconde (très improbable au MVP). Si ça devient un problème, basculer vers une table `receipt_sequences` séparée.

## Index de performance

Synthèse de tous les index, par table, avec leur justification :

### `users`

- `uq_users_email` (UNIQUE) : login par email, contrainte d'unicité
- `idx_users_email` : déjà couvert par UNIQUE, mais explicite pour la lisibilité

### `email_verification_tokens` et `password_reset_tokens`

- `idx_*_user_id` : récupérer tous les tokens d'un user (purge, vérif)
- `idx_*_expires_at` : purge des tokens expirés via cron

### `stores`

- `idx_stores_owner_id` : retrouver la boutique d'un user après login
- `uq_stores_owner` (UNIQUE) : 1 boutique par user

### `products`

- `idx_products_store_name` (composite, partiel sur deleted_at IS NULL) : recherche par nom dans une boutique active
- `idx_products_store_barcode` (composite, partiel) : scan code-barres
- `uq_products_store_barcode_active` (UNIQUE partiel) : un code-barres unique par boutique parmi les actifs

### `sales`

- `idx_sales_store_created_at` (composite, DESC sur created_at) : historique des ventes par boutique, du plus récent au plus ancien
- `idx_sales_store_receipt_number` (composite) : recherche par numéro de reçu
- `uq_sales_store_receipt_number` (UNIQUE composite) : intégrité du numéro séquentiel

### `sale_items`

- `idx_sale_items_sale_id` : lister les lignes d'une vente
- `idx_sale_items_store_id` : RLS efficient
- `idx_sale_items_product_id` (partiel) : lister les ventes d'un produit (analytics futurs)

**Total** : ~15 index. Volume estimé après 1 an d'usage MVP (50 stores, 100 ventes/jour/store, 3 lignes par vente) : ~5,5M lignes dans `sale_items`. Les index restent efficients à ce volume.

## Décisions structurantes

### Pourquoi `receipt_number` est généré au sync, pas en local

Décision validée : INTEGER séquentiel généré côté serveur via le trigger `generate_receipt_number`.

**Conséquence métier importante** : en mode hors-ligne, le reçu imprimé immédiatement n'a PAS de numéro de reçu fiscal valide. Trois options pour le MVP :

1. **Imprimer un "ticket de caisse" provisoire** sans numéro DGI, et imprimer un "reçu fiscal" définitif après sync (réimpression à la demande).
2. **Imprimer deux fois** : un ticket immédiat + un reçu fiscal au retour de la connexion (à donner au client si demandé).
3. **Différer l'impression** : ne pas imprimer en mode offline, attendre le retour de la connexion.

L'option 1 semble la plus pragmatique. À valider avec un expert-comptable ivoirien avant production. Ce point est documenté dans la todo `docs/data-model.md > TODO pour la phase DDL détaillée`.

### Pourquoi `NUMERIC(12, 2)` pour les montants

- 12 chiffres, dont 2 décimales = montant max de 9 999 999 999,99 (≈ 10 milliards). Largement suffisant.
- Le FCFA n'a pas de subdivision en pratique, mais on garde 2 décimales pour :
  - Anticipation multi-devises (EUR, USD avec centimes)
  - Calculs de TVA intermédiaires qui peuvent produire des décimales
  - Cohérence avec les pratiques comptables internationales

### Pourquoi pas d'audit log au MVP

Décision documentée. Conséquences :

- Pas de traçabilité "qui a modifié le prix du produit X et quand" hors des `created_at`/`updated_at` actuels.
- Pas de log des connexions, des consultations, des suppressions.

À ajouter en Phase 2 si besoin réglementaire. Si on l'ajoute, prévoir une table `audit_log` partitionnée par mois (sinon ça grossit vite).

### Pourquoi hard delete avec ON DELETE RESTRICT

- Conformité RGPD : on doit pouvoir supprimer un user qui le demande.
- Intégrité des ventes : on ne doit pas pouvoir orphelinèr les ventes.
- Solution : pour supprimer un user, on doit d'abord :
  1. Anonymiser : `email = 'deleted-{uuid}@anonymous'`, `phone = NULL`, etc.
  2. Soft-delete les produits associés
  3. **Garder les ventes intactes** (obligation comptable)
  4. Marquer le store comme inactif (à ajouter en Phase 2 si besoin)

Cette procédure est manuelle au MVP, à automatiser en Phase 2 via un endpoint admin.

## Volume de la base après 1 an MVP estimé

Hypothèses : 50 stores actifs, 100 ventes/jour/store, 3 lignes par vente, 200 produits par store en moyenne.

| Table | Lignes | Taille estimée |
|---|---|---|
| `users` | ~50 | < 1 Mo |
| `stores` | ~50 | < 1 Mo |
| `products` | ~10 000 | ~5 Mo |
| `sales` | ~1 825 000 | ~500 Mo |
| `sale_items` | ~5 475 000 | ~1,5 Go |
| Index | — | ~800 Mo |
| **Total** | — | **~3 Go** |

Largement supportable par un VPS Hetzner CPX11 (40 Go SSD). À surveiller au-delà de 5 ans ou si le nombre de stores explose.

## Références

- [data-model.md](data-model.md) — Vue d'ensemble et conventions
- [adr/0002-multi-tenancy-rls.md](adr/0002-multi-tenancy-rls.md) — Justification du RLS
- [adr/0003-sync-hybride.md](adr/0003-sync-hybride.md) — Justification du modèle de sync
- [.claude/rules/migrations-safety.md](.claude/rules/migrations-safety.md) — Règles strictes pour les migrations
