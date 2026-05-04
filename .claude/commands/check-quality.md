---
description: Lance toutes les vérifications de qualité avant un commit
---

# /check-quality

Lance la suite complète de vérifications avant de committer. À utiliser systématiquement avant un `git commit`.

## Étapes

### Backend (si des fichiers de `backend/` ont été modifiés)

1. `cd backend && make format` — formate le code
2. `cd backend && make lint` — vérifie sans modifier (échoue si problème)
3. `cd backend && make type-check` — mypy strict
4. `cd backend && make test` — tests pytest
5. Si une migration a été ajoutée : tester `alembic upgrade head` puis `alembic downgrade -1`

### Mobile (si des fichiers de `mobile/` ont été modifiés)

1. `cd mobile && make format` — formate
2. `cd mobile && make analyze` — vérifie statiquement
3. `cd mobile && make test` — tests

## En cas d'échec

- Si `format` modifie des fichiers : c'est OK, c'est ce qu'on veut. Re-staged les fichiers.
- Si `lint` ou `analyze` échoue : corriger les warnings/erreurs avant de commit.
- Si `type-check` échoue : ajouter les annotations manquantes ou corriger.
- Si un test échoue : ne PAS commit, corriger le test ou le code d'abord.

## Si tout passe

Confirmer à l'utilisateur que tout est vert et proposer le message de commit en suivant Conventional Commits :

```
type(scope): short description

Optional longer body.
```

Types courants : `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`.
Scopes courants : `backend`, `mobile`, `auth`, `catalog`, `sales`, `sync`, `infra`, `docs`.
