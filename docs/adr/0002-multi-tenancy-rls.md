# ADR-0002 : Multi-tenancy via store_id + Row-Level Security PostgreSQL

## Statut

Accepté — 29 avril 2026

## Contexte

Le système POS Mobile CI est multi-tenant : plusieurs commerçants utilisent la même infrastructure (même API, même base de données) mais leurs données doivent être strictement isolées les unes des autres.

Le risque le plus critique pour ce produit est une **fuite de données entre tenants** : un commerçant qui verrait les ventes ou les produits d'un autre. Conséquences potentielles : perte de confiance massive, atteinte à la concurrence commerciale, problèmes juridiques.

Contraintes :

- Un seul développeur, donc risque accru de bug applicatif (oubli de filtre `WHERE store_id = ?`)
- Besoin d'une isolation forte qui résiste aux erreurs de code
- Performance acceptable (le RLS ne doit pas dégrader gravement les requêtes)
- Compatibilité avec SQLAlchemy 2.0 et Alembic

## Décision

Multi-tenancy basée sur deux mécanismes complémentaires :

1. **Colonne `store_id` sur toutes les tables tenant**, avec contrainte NOT NULL et index systématique.
2. **Row-Level Security PostgreSQL activé sur ces tables**, avec une politique qui filtre automatiquement par le `store_id` courant injecté dans la session.

Le `store_id` courant est injecté à chaque requête authentifiée via une variable de session :

```sql
SET LOCAL app.current_store_id = '<uuid_du_jwt>';
```

Et la politique RLS filtre :

```sql
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_products_tenant_isolation ON products
  USING (store_id = current_setting('app.current_store_id', true)::uuid)
  WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);
```

Le middleware FastAPI extrait le `store_id` du JWT et l'injecte dans la session PostgreSQL avant de transmettre la requête au handler.

## Alternatives considérées

### Schema-per-tenant

Un schéma PostgreSQL par boutique (`tenant_abc.products`, `tenant_xyz.products`).

**Rejeté.** Avantages : isolation très forte au niveau du moteur. Inconvénients :

- Migrations Alembic nettement plus complexes (appliquer à N schémas)
- Pool de connexions à gérer par schéma
- Backup/restore plus compliqué
- Pas adapté à une croissance > 100 tenants (limite PostgreSQL pratique sur le nombre de schémas)

### Database-per-tenant

Une base PostgreSQL par boutique.

**Rejeté.** Cauchemar opérationnel pour un solo dev. N backups, N migrations, N pools de connexion. Adapté uniquement aux clients enterprise très exigeants en isolation, pas du tout à des PME ivoiriennes.

### `store_id` côté code uniquement (sans RLS)

Filtrage par `store_id` uniquement dans les requêtes SQLAlchemy applicatives, sans filet de sécurité côté DB.

**Rejeté.** C'est l'approche la plus courante mais la plus risquée. **Une seule erreur de code** (oublier un `WHERE` dans une jointure complexe, un `SELECT *` mal sécurisé) suffit à faire fuiter des données entre tenants. Pour un solo dev qui code vite, c'est un trop gros risque.

### Tenant-aware ORM avec listener SQLAlchemy

Implémenter un `before_compile` SQLAlchemy qui ajoute automatiquement un `WHERE store_id = ?` à toutes les requêtes.

**Rejeté.** Approche élégante en théorie mais fragile : ne couvre pas les requêtes raw SQL, peut être bypassée par des relations chargées en lazy loading, et l'erreur de configuration n'est pas évidente. Le RLS PostgreSQL est plus robuste car il opère au niveau du moteur de DB lui-même.

## Conséquences

### Positives

- **Isolation en profondeur** : même un bug applicatif ne peut pas exposer les données d'un autre tenant. Le moteur DB filtre tout seul.
- Mécanisme natif PostgreSQL, mature et stable depuis 2016 (PostgreSQL 9.5+)
- Aucun changement d'API SQLAlchemy : on écrit des requêtes normales, RLS filtre transparentement
- Performance acceptable : RLS utilise les index normaux. Une requête `SELECT * FROM products` devient en réalité `SELECT * FROM products WHERE store_id = ?` qui hit l'index `idx_products_store_id_*`.

### Négatives

- **RLS est invisible** : un dev qui débugge peut être surpris qu'une requête renvoie 0 lignes alors que les données existent. Documentation et formation indispensables.
- **Migrations RLS doivent être écrites manuellement** : Alembic ne détecte pas automatiquement les changements de politiques RLS. Process à respecter strictement.
- **Tests doivent vérifier le RLS** : il faut écrire des tests qui simulent un user A tentant d'accéder aux données d'un user B et vérifient que c'est bloqué.
- **Connexion DB unique partagée** : il faut s'assurer que le `SET LOCAL app.current_store_id` est bien fait à chaque requête et que la session est nettoyée après. Risque de fuite de session sinon.
- **Performance du RLS sur jointures complexes** : à surveiller, le RLS multiplie les filtres sur chaque table jointe. Acceptable au volume MVP mais à monitorer.

### Neutres

- Convention forte à respecter : toute nouvelle table métier doit avoir `store_id` + RLS dès la première migration. Ne pas oublier dans le checklist de revue de migration.

## Implémentation

### Side notes pour le code

Middleware FastAPI :

```python
@app.middleware("http")
async def set_store_id_in_session(request, call_next):
    token = extract_jwt(request)
    if token:
        store_id = decode_jwt(token).get("store_id")
        async with get_db() as session:
            await session.execute(
                text("SET LOCAL app.current_store_id = :sid"),
                {"sid": str(store_id)}
            )
    return await call_next(request)
```

Test critique à écrire :

```python
async def test_user_a_cannot_read_products_of_user_b(client_a, client_b):
    product_b = await create_product(client_b, name="Pain de B")
    response = await client_a.get(f"/api/v1/products/{product_b.id}")
    assert response.status_code == 404  # pas 200 ni 403
```

## Critères qui justifieraient de revisiter cette décision

- Performance dégradée sur des requêtes complexes (à mesurer avec EXPLAIN ANALYZE)
- Migration vers une autre DB qui ne supporte pas le RLS (peu probable, on reste sur PostgreSQL)
- Besoin d'isolation encore plus forte (clients enterprise) qui justifierait schema-per-tenant
