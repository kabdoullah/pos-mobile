---
description: Crée un nouveau module backend FastAPI avec la structure standard
---

# /new-module

Crée un nouveau module backend FastAPI dans `backend/app/modules/` en suivant la structure standard du projet.

## Étapes

1. Demander à l'utilisateur :
   - Le nom du module (snake_case, en anglais, pluriel — ex: `invoices`, `customers`)
   - Une description courte de ce que fait le module

2. Créer la structure :
   ```
   backend/app/modules/<name>/
   ├── __init__.py
   ├── router.py
   ├── service.py
   ├── repository.py
   ├── schemas.py
   ├── models.py
   └── exceptions.py  (optionnel, seulement si exceptions spécifiques)
   ```

3. Pré-remplir chaque fichier avec un squelette minimal cohérent avec les conventions du projet (voir `.claude/rules/backend-conventions.md` et le module `auth` comme référence) :
   - `router.py` : `APIRouter()` avec un endpoint placeholder GET `/`
   - `service.py` : classe `<Name>Service` qui prend `db: AsyncSession`
   - `repository.py` : classe `<Name>Repository` qui prend `db: AsyncSession`
   - `schemas.py` : commentaire de placeholder
   - `models.py` : commentaire de placeholder

4. Inclure le router dans `backend/app/main.py` :
   ```python
   from app.modules.<name>.router import router as <name>_router
   app.include_router(<name>_router, prefix=f"{api_v1_prefix}/<name>", tags=["<name>"])
   ```

5. Importer les modèles dans `backend/alembic/env.py` :
   ```python
   from app.modules.<name> import models as <name>_models  # noqa: F401
   ```

6. Rappeler à l'utilisateur les prochaines étapes :
   - Définir les modèles SQLAlchemy dans `models.py`
   - Définir les schémas Pydantic dans `schemas.py`
   - Implémenter le repository et le service
   - Générer la migration : `/new-migration`
   - Écrire les tests dans `backend/tests/test_<name>.py`
