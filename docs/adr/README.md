# Architecture Decision Records (ADR)

Ce dossier regroupe les décisions d'architecture importantes prises au cours du projet, dans l'ordre chronologique.

## Qu'est-ce qu'un ADR ?

Un ADR est un document court qui trace une décision d'architecture avec son **contexte** (pourquoi on s'est posé la question), la **décision** prise, les **alternatives considérées**, et les **conséquences** acceptées.

Pourquoi écrire des ADRs :

- **Mémoire à long terme** : dans 6 mois, tu te demanderas pourquoi tu as fait tel choix. L'ADR est la réponse.
- **Onboarding** : si quelqu'un rejoint le projet, lire les ADRs lui donne le raisonnement, pas seulement le résultat.
- **Pression sur la rigueur** : écrire un ADR force à clarifier sa pensée avant de coder.
- **Réversibilité explicite** : un ADR peut être marqué comme `superseded` par un autre, sans réécrire l'histoire.

## Liste

| # | Titre | Statut | Date |
|---|---|---|---|
| [0001](0001-monolithe-modulaire.md) | Monolithe modulaire FastAPI | Accepté | 2026-04-29 |
| [0002](0002-multi-tenancy-rls.md) | Multi-tenancy via store_id + Row-Level Security PostgreSQL | Accepté | 2026-04-29 |
| [0003](0003-sync-hybride.md) | Synchronisation hybride événementiel + état | Accepté | 2026-04-29 |
| [0004](0004-auth-email-pin.md) | Authentification email + mot de passe + PIN local | Accepté | 2026-04-29 |
| [0005](0005-stack-flutter-fastapi.md) | Stack Flutter + FastAPI + PostgreSQL 100% open source | Accepté | 2026-04-29 |
| [0006](0006-hebergement-hetzner.md) | Hébergement VPS Hetzner avec Docker Compose | Accepté | 2026-04-29 |

## Comment écrire un nouvel ADR

1. Copier le template `_template.md` (à créer)
2. Numéroter incrémentalement : si le dernier est `0006`, ton ADR sera `0007-mon-titre.md`
3. Utiliser des kebab-case courts dans le nom de fichier
4. Mettre à jour la table ci-dessus
5. Statut initial : `Proposé` tant que ce n'est pas tranché, puis `Accepté`, `Rejeté`, ou `Superseded by ADR-XYZ`

## Quand écrire un ADR

À écrire pour toute décision qui :

- A un impact long terme et coûte cher à inverser
- Implique un trade-off non trivial
- Sera questionnée plus tard ("pourquoi on a fait X et pas Y ?")
- Concerne la sécurité, la perf, ou l'évolutivité

À ne PAS écrire pour :

- Les choix de bibliothèque mineurs (ex: choix entre 2 packages d'utilitaires)
- Les détails d'implémentation
- Les conventions de style de code (à mettre dans un `STYLE_GUIDE.md` séparé)
