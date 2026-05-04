# Configuration Claude Code

Ce dossier configure [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) pour ce projet. Tout est versionné dans Git pour que la config soit partagée si l'équipe grossit.

## Structure

```
.claude/
├── README.md                  Ce fichier
├── settings.json              Hooks configurés
├── rules/                     Règles contextuelles (path-scoped)
│   ├── backend-conventions.md
│   ├── mobile-conventions.md
│   └── migrations-safety.md
├── commands/                  Slash commands réutilisables
│   ├── new-adr.md
│   ├── new-migration.md
│   ├── new-module.md
│   └── check-quality.md
├── hooks/                     Scripts shell exécutés automatiquement
│   ├── auto-format.sh
│   └── block-dangerous-commands.sh
└── skills/                    Skills (vide pour le MVP, à utiliser plus tard)
```

## Comment ça fonctionne

### CLAUDE.md (à la racine du repo)

Court (< 200 lignes), chargé à chaque session. Contient les règles globales et pointe vers les autres ressources via `@path`. Voir `../CLAUDE.md`.

### Rules (`.claude/rules/`)

Fichiers Markdown avec frontmatter YAML (`globs`) qui les fait charger UNIQUEMENT quand Claude touche aux fichiers correspondants. Évite de polluer le contexte.

Exemple : `backend-conventions.md` ne se charge que quand on édite des fichiers `backend/**/*.py`.

### Commands (`.claude/commands/`)

Slash commands disponibles dans Claude Code. Chaque fichier `.md` devient une commande.

Commandes disponibles :

- `/new-adr` — Crée un nouvel ADR numéroté
- `/new-migration` — Génère une migration Alembic en respectant les règles RLS
- `/new-module` — Crée un nouveau module backend complet
- `/check-quality` — Lance toutes les vérifications avant commit

### Hooks (`.claude/hooks/`)

Scripts shell exécutés automatiquement à des points précis du workflow Claude Code. Contrairement à CLAUDE.md (suivi à ~70%), les hooks sont **garantis à 100%**.

Hooks configurés :

- **PostToolUse sur Edit/Write/MultiEdit** → `auto-format.sh`
  Formate automatiquement les fichiers Python (ruff) et Dart après édition. Garantit que tout fichier édité par Claude est conforme aux conventions du projet.

- **PreToolUse sur Bash** → `block-dangerous-commands.sh`
  Bloque les commandes destructrices (`rm -rf /`, `git push --force` sur main, `DROP DATABASE`, `DELETE FROM sales`, etc.).

## Comment Claude Code utilise tout ça

1. Au démarrage d'une session : lit `CLAUDE.md` à la racine
2. Quand on lui demande quelque chose qui touche `backend/**/*.py` : charge `rules/backend-conventions.md`
3. Quand il édite un fichier : `auto-format.sh` se déclenche en arrière-plan
4. Quand il veut lancer une commande Bash : `block-dangerous-commands.sh` la valide d'abord

## Démarrer avec Claude Code

```bash
# Installer Claude Code (Node.js 18+ requis)
npm install -g @anthropic-ai/claude-code

# Dans le dossier du projet
cd pos-mobile
claude

# Première étape recommandée : laisser Claude analyser le projet
> /init

# Pour des tâches non triviales : toujours utiliser le plan mode
> Shift+Tab Shift+Tab  # bascule en plan mode
```

## Plan mode

Le plan mode est crucial en mode solo : il force Claude à présenter un plan avant d'exécuter, ce qui évite les corrections en chaîne.

**Règle** : pour toute tâche qui implique plus que la modification triviale d'un fichier, utiliser plan mode.

## Iterating sur la config

Cette config évolue avec le projet. Quand quelque chose ne marche pas :

- Si Claude oublie une convention : c'est probablement que CLAUDE.md est trop long ou que la rule n'a pas le bon glob
- Si Claude fait une erreur destructrice : ajouter le pattern dans `block-dangerous-commands.sh`
- Si Claude fait une action répétitive : créer un slash command dans `.claude/commands/`

Voir https://code.claude.com/docs/en/best-practices pour les bonnes pratiques officielles.

## Limitations connues

- Les hooks shell ne fonctionnent pas sur Windows natif (utiliser WSL2)
- `auto-format.sh` essaie d'utiliser `uv run ruff` puis fallback sur `ruff` direct ; nécessite que `uv` ou `ruff` soit dans le PATH
- Les hooks Bash sont en best-effort : si `dart format` n'est pas dans le PATH, le hook ne formate pas mais ne bloque pas non plus
