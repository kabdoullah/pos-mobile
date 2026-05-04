# Configuration GitHub à faire après le premier push

> Document one-shot. À supprimer ou archiver une fois les configurations appliquées.
> Dernière mise à jour : 29 avril 2026.

Quand tu pousses ce repo sur GitHub pour la première fois, voici les configurations à appliquer dans les paramètres du repo. Ces réglages protègent ta branche `main` contre les pushs accidentels et garantissent que la CI passe avant chaque merge.

## 1. Branch protection sur `main`

**Chemin** : Settings > Branches > Add branch protection rule

### Branch name pattern

```
main
```

### Réglages à activer

- [x] **Require a pull request before merging**
  - [x] Require approvals : `0` (tu es solo, pas besoin de te valider toi-même)
  - [x] Dismiss stale pull request approvals when new commits are pushed
  - [ ] Require review from Code Owners *(pas pertinent en solo)*

- [x] **Require status checks to pass before merging**
  - [x] Require branches to be up to date before merging
  - **Status checks requis** (à ajouter un par un, ils apparaissent après le 1er run de chaque workflow) :
    - `Lint & format check` *(de Backend CI)*
    - `Type check (mypy)` *(de Backend CI)*
    - `Tests (pytest with PostgreSQL)` *(de Backend CI)*
    - `Format & analyze` *(de Mobile CI)*
    - `Tests` *(de Mobile CI)*
    - `Run pre-commit hooks` *(de Pre-commit hooks)*

  > Note : ces checks n'apparaîtront dans la liste qu'après leur première exécution. Pousse une PR de test, attends que les workflows tournent une fois, puis viens cocher les checks ici.

- [x] **Require conversation resolution before merging**
  *(force à fermer toutes les conversations de review avant merge — utile même en solo pour ne pas oublier des TODO)*

- [x] **Require linear history**
  *(force le rebase ou squash merge, évite les merge commits — historique plus propre)*

- [ ] **Require deployments to succeed before merging**
  *(à activer plus tard quand tu auras un environnement de staging)*

- [x] **Do not allow bypassing the above settings**
  *(t'empêche de bypasser tes propres règles "vite fait" — discipline)*

- [x] **Restrict who can push to matching branches**
  - Cocher pour t'inclure toi-même
  - Personne d'autre ne pourra push directement sur main

- [x] **Allow force pushes** : ❌ DÉCOCHÉ
- [x] **Allow deletions** : ❌ DÉCOCHÉ

## 2. Secrets GitHub à configurer

**Chemin** : Settings > Secrets and variables > Actions

### Secrets nécessaires immédiatement

Aucun pour le moment. Les workflows actifs (CI tests/lint) n'utilisent que des secrets de test générés à la volée.

### Secrets à ajouter quand tu activeras le déploiement

Voir le commentaire en tête de `.github/workflows/deploy-prod.yml`. Les secrets requis seront :

- `VPS_HOST` — IP ou DNS du VPS Hetzner
- `VPS_USER` — utilisateur SSH (ex: `pos`)
- `VPS_SSH_KEY` — clé privée SSH (format ed25519 recommandé)
- `VPS_DEPLOY_PATH` — chemin du repo sur le VPS (ex: `/home/pos/pos-mobile-ci`)

## 3. Settings du repo (autres)

**Chemin** : Settings > General

### Pull Requests

- [x] Allow squash merging *(recommandé : squash en un seul commit)*
- [ ] Allow merge commits *(à éviter, casse l'historique linéaire)*
- [ ] Allow rebase merging *(OK aussi mais plus risqué pour les conflits)*
- [x] Always suggest updating pull request branches
- [x] Automatically delete head branches *(supprime automatiquement la branche de feature après merge)*

### Default branch

- Vérifier que `main` est bien la branche par défaut.

### Features

- [x] Issues *(pour tracer ton backlog si tu n'utilises pas un autre outil)*
- [ ] Wikis *(la doc est dans `docs/` du repo, pas besoin de wiki dupliqué)*
- [ ] Projects *(facultatif, peut servir de Kanban)*
- [ ] Discussions *(pas pertinent en solo)*

### Pull Requests > Allow auto-merge

- [x] Activer auto-merge
  *(permet de marquer une PR comme "merge automatiquement quand la CI passe", très utile)*

## 4. Configuration de l'environnement `production` (pour plus tard)

**Chemin** : Settings > Environments > New environment

Quand tu activeras le déploiement, créer un environnement nommé `production` avec :

- [x] **Required reviewers** : toi-même
  *(force une approbation manuelle avant chaque déploiement, garde-fou utile)*

- [x] **Deployment branches** : Selected branches > `main` uniquement
  *(empêche un déploiement depuis une branche de feature par erreur)*

## 5. Validation

Après avoir tout configuré, fais le test suivant :

1. Crée une branche `test/branch-protection`
2. Modifie un fichier (ex: ajoute une ligne au README)
3. Pousse la branche et ouvre une PR
4. Vérifie que :
   - Les workflows CI se déclenchent automatiquement
   - Le bouton "Merge" est grisé tant que la CI n'est pas verte
   - Tu ne peux pas push directement sur `main` (`git push origin main` doit échouer)
5. Une fois la CI verte, merge la PR
6. Vérifie que la branche est automatiquement supprimée

Si tout marche, ferme cette todo. Si quelque chose cloche, rouvre les paramètres.

## 6. Bonus : badges dans le README

Une fois que les workflows tournent au moins une fois, tu peux ajouter ces badges en tête du `README.md` principal :

```markdown
[![Backend CI](https://github.com/<ton-user>/<ton-repo>/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/<ton-user>/<ton-repo>/actions/workflows/backend-ci.yml)
[![Mobile CI](https://github.com/<ton-user>/<ton-repo>/actions/workflows/mobile-ci.yml/badge.svg)](https://github.com/<ton-user>/<ton-repo>/actions/workflows/mobile-ci.yml)
[![Pre-commit](https://github.com/<ton-user>/<ton-repo>/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/<ton-user>/<ton-repo>/actions/workflows/pre-commit.yml)
```

Remplace `<ton-user>/<ton-repo>` par ton vrai chemin GitHub.

---

> Une fois cette configuration appliquée, **supprime ce fichier** ou archive-le dans `docs/setup/`. Il ne sert qu'au setup initial.
