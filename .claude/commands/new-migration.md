---
description: Génère une nouvelle migration Alembic en suivant les règles de sécurité du projet
---

# /new-migration

Génère une nouvelle migration Alembic pour le backend.

## Étapes

1. Demander à l'utilisateur le message de la migration (ex: "add products table")
2. Vérifier que les modèles SQLAlchemy concernés sont bien importés dans `backend/alembic/env.py`. Si non, l'ajouter.
3. Lancer `cd backend && make makemigration MSG="<message>"`
4. **Lire le fichier de migration généré et l'afficher à l'utilisateur** pour relecture
5. **Si la migration crée une nouvelle table tenant** (avec colonne `store_id`) :
   - Ajouter MANUELLEMENT les commandes RLS dans `upgrade()` :
     ```python
     op.execute("ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;")
     op.execute("""CREATE POLICY rls_<table>_tenant_isolation ON <table>
                  USING (store_id = current_setting('app.current_store_id', true)::uuid)
                  WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);""")
     ```
   - Ajouter les commandes inverses dans `downgrade()`
6. **Si la migration crée une table avec `updated_at`**, ajouter le trigger :
   ```python
   op.execute("""CREATE TRIGGER set_updated_at BEFORE UPDATE ON <table>
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();""")
   ```
7. Demander à l'utilisateur de tester `alembic upgrade head` puis `alembic downgrade -1`
8. Rappeler à l'utilisateur d'écrire un test d'isolation RLS si c'est une table tenant

## Règles à respecter (depuis `.claude/rules/migrations-safety.md`)

- Les politiques RLS ne sont JAMAIS auto-détectées par Alembic, toujours les ajouter manuellement
- Les triggers `updated_at` non plus
- Toujours tester upgrade ET downgrade
- Documenter en docstring si la migration n'est pas reversible
