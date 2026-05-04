---
description: Règles de sécurité strictes sur les migrations Alembic
globs:
  - "backend/alembic/versions/*.py"
  - "backend/app/modules/**/models.py"
---

# Migrations Alembic — règles strictes

Les migrations DB sont l'opération la plus risquée du backend. Une migration ratée en production peut corrompre les données de tous les commerçants.

## Avant de générer une migration

1. **Vérifier que les modèles SQLAlchemy sont importés** dans `backend/alembic/env.py`. Sinon Alembic ne les détectera pas.
2. **Lire le diff de la migration** générée par `make makemigration MSG="..."` AVANT de la commit.
3. **Renommer le fichier** si la date n'est pas explicite (le format par défaut est OK).

## Politiques RLS — Alembic ne les détecte pas

Quand on ajoute une nouvelle table tenant (avec `store_id`), il faut TOUJOURS ajouter manuellement dans la migration :

```python
def upgrade() -> None:
    # ... la création de la table ...
    op.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_products_tenant_isolation ON products
        USING (store_id = current_setting('app.current_store_id', true)::uuid)
        WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);
    """)

def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_products_tenant_isolation ON products;")
    op.execute("ALTER TABLE products DISABLE ROW LEVEL SECURITY;")
    # ... drop de la table ...
```

## Triggers updated_at

Idem, pas auto-détecté par Alembic. Ajouter manuellement :

```python
op.execute("""
    CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
""")
```

## Avant de commit

- [ ] Lire le diff de la migration ligne par ligne
- [ ] Tester `alembic upgrade head` sur une DB de dev
- [ ] Tester `alembic downgrade -1` (sauf si migration de données irréversible — auquel cas le documenter explicitement dans le docstring)
- [ ] Vérifier que les politiques RLS sont présentes pour toute nouvelle table tenant
- [ ] Vérifier que le test d'isolation (user A ne lit pas les données de user B) passe

## Migrations de données

Si la migration modifie des données (pas seulement le schéma) :

- Wrapper dans une transaction si possible
- Utiliser `op.execute()` avec du SQL raw plutôt que des modèles SQLAlchemy (les modèles peuvent évoluer et casser les anciennes migrations)
- Documenter clairement dans le docstring de la migration ce qu'elle fait
- Backup obligatoire en production AVANT d'appliquer (voir `docs/runbook.md`)

## Règle d'or

**Une migration en production sans backup récent est interdite.** Le runbook documente la procédure (`./scripts/backup-now.sh`).

## Référence

La migration initiale `0001_initial_schema.py` est l'exemple complet à suivre. Elle contient :
- Création des extensions pgcrypto et pg_trgm
- Type ENUM `payment_method_enum`
- Fonctions trigger : `update_updated_at_column`, `prevent_sales_modification`, `generate_receipt_number`
- 7 tables avec contraintes complètes
- Politiques RLS sur 4 tables tenant
- Triggers `updated_at` sur 3 tables
- Triggers d'immuabilité sur `sales`
- Trigger atomique de génération du `receipt_number`
- Downgrade complet et inverse

Voir aussi `docs/data-model-detailed.md` pour la justification de chaque choix.
