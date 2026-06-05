# Grille de scoring — Flutter UI/UX Optimizer POS

## UI Score (sur 10)

| Critère | Poids | 0 pt | 1 pt | 2 pts |
|---------|-------|------|------|-------|
| Hiérarchie visuelle | 2 | Aucune structure | Partielle | Claire, 1 CTA principal |
| Cohérence Material 3 | 2 | Full M2 ou palette non-conforme | Mix M2/M3 | Full M3 + palette POS |
| Contrastes & lisibilité | 2 | < 3:1 | 3:1–4.5:1 | ≥ 4.5:1 (WCAG AA) |
| Espacement & densité | 2 | Incohérent, trop serré | Approximatif | Grille 4dp respectée |
| Qualité visuelle globale | 2 | Amateur / daté | Correct | Professionnel / sobre Wave |

## UX Score (sur 10)

| Critère | Poids | 0 pt | 1 pt | 2 pts |
|---------|-------|------|------|-------|
| Feedback utilisateur | 2 | Absent | Partiel | Complet (loading, erreur, succès) |
| Clarté des actions | 2 | Actions cachées | Ambiguës | Immédiates et évidentes |
| Gestion des 4 états | 2 | Aucun état géré | 1-2 états | loading / error / empty / data |
| Parcours utilisateur | 2 | Friction élevée | Quelques frictions | Fluide |
| Responsive | 2 | Non responsive | Partiellement | 360px → 480px sans overflow |

## Accessibilité (sur 10)

| Critère | Poids | Score |
|---------|-------|-------|
| Contrastes WCAG AA (≥ 4.5:1 texte) | 3 | /3 |
| Zones tactiles ≥ 48×48px | 2 | /2 |
| `tooltip` sur tous les `IconButton` | 2 | /2 |
| Taille de texte minimale (body ≥ 14sp) | 2 | /2 |
| `excludeFromSemantics` sur décoratifs | 1 | /1 |

## Qualité code Flutter (sur 10)

| Critère | Poids | Score |
|---------|-------|-------|
| `const` sur widgets statiques | 2 | /2 |
| Zéro couleur/style hardcodé | 2 | /2 |
| Widgets < 80 lignes (découpage) | 2 | /2 |
| Zéro `dynamic`, zéro `print()` | 2 | /2 |
| `/// doc` sur classes/méthodes publiques | 2 | /2 |