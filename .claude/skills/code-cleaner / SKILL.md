---
name: code-cleaner
description: >
  Nettoie du code source en supprimant les commentaires inutiles et les emojis.
  Déclencher quand l'utilisateur mentionne : supprimer commentaires, enlever emojis,
  nettoyer le code, retirer les commentaires inutiles, code trop commenté, commentaires
  évidents, purger les emojis du code, nettoyer fichier dart/python/js/ts/etc.,
  clean code, remove comments, strip emojis, clean up comments, trop de commentaires,
  nettoyer tous les fichiers, clean multiple files, clean this PR.
  Fonctionne sur tous les langages : Dart, Python, JS, TS, Kotlin, Swift, Java, Go, etc.
  Préserve TOUJOURS la logique métier, les commentaires utiles (TODO actionnable,
  doc publique, licence, explication non-évidente) et tout le code fonctionnel.
---

# Code Cleaner

## RÔLE

Supprimer le bruit visuel du code : commentaires évidents, emojis hors UI, blocs
décoratifs, code mort commenté. Ne jamais modifier la logique, la structure, les
imports, ni l'indentation.

---

## MODE D'UTILISATION

| Invocation | Comportement |
|---|---|
| `/code-cleaner <fichier>` | Nettoie un fichier, affiche résumé + code complet |
| `/code-cleaner --quick <fichier>` | Nettoie sans résumé, code complet directement |
| `/code-cleaner --diff <fichier>` | Affiche uniquement le diff (utile sur grands fichiers) |
| `/code-cleaner <glob>` | Nettoie plusieurs fichiers, un à la fois avec résumé groupé |

---

## RÈGLES DE SUPPRESSION

### Emojis — supprimer TOUJOURS (sauf UI utilisateur)

Tout caractère emoji dans le code source : commentaires, logs, noms de variables,
messages d'erreur, print/logger calls.

```dart
// AVANT
_log.i('✅ Sale created: $id');
// ✨ Amélioration: contraste amélioré
final color = Colors.green; // 🎨

// APRÈS
_log.i('Sale created: $id');
// Amélioration: contraste amélioré
final color = Colors.green;
```

**Exception** : strings affichées à l'utilisateur final (UI text, SnackBar, Toast)
où l'emoji est intentionnel → **conserver**.

```dart
// GARDER — visible dans l'UI
SnackBar(content: Text('✅ Vente enregistrée'));
```

---

### Commentaires en ligne (`//`, `#`, `--`)

#### Supprimer si…

**Dit exactement ce que le code dit**
```dart
i++; // incrémente i
return total; // retourne le total
final user = User(); // crée un User
```

**Répète le nom de la fonction/classe/variable**
```dart
// Calcule le total
Decimal get total => ...

// Initialise le notifier
@override
Future<void> build() async { ... }
```

**Séparateur décoratif ou ligne vide de commentaire**
```dart
// ============================================================
// ---
// ***
//
```

**Code mort commenté** (y compris imports commentés)
```dart
// final oldPrice = item.price * 1.2;
// import 'package:old_pkg/old_pkg.dart';
// print('debug: $value');
```

**Placeholder vide ou générique**
```dart
// TODO
// fix this
// temp
// hack
// ???
// ...
```

**Bloc `#region` / `#endregion`** (artefact VS)
```ts
// #region Helpers
// #endregion
```

---

### Blocs multi-lignes (`/* */`, `/** */`, `"""`, `'''`)

Appliquer les mêmes règles que pour les commentaires en ligne.

**Supprimer si le bloc...**
- Répète la signature de la fonction (docstring évidente)
- Ne contient que des séparateurs ou du texte générique
- Est du code mort multi-lignes

```python
# Supprimer
def calculate_total(items):
    """Calculate total."""  # répète le nom
    ...

# Supprimer
/*
 * ================================
 * Helper section
 * ================================
 */
```

**Conserver si le bloc...**
- Est une doc publique avec description utile
- Contient une explication non-évidente
- Est une licence ou en-tête de fichier

```python
# Garder
def parse_amount(raw: str) -> Decimal:
    """
    Parse un montant FCFA depuis l'API.

    Utilise Decimal (pas float) pour éviter les erreurs d'arrondi
    sur les grands entiers FCFA (ex: 1_000_000 FCFA).
    """
```

---

### Lignes vides consécutives

Après suppression de commentaires, des blocs vides apparaissent.
**Règle** : max 2 lignes vides consécutives dans un fichier, max 1 à l'intérieur d'une fonction.
Réduire les excès silencieusement — ne pas les signaler dans le résumé.

---

#### Conserver si le commentaire…

**Explique un POURQUOI non-évident**
```dart
// On parse en Decimal ici et non en double pour éviter les erreurs
// d'arrondi sur les montants en FCFA (ex: 1500.5 * 3 != 4501.5 en float).
final total = Decimal.parse(raw) * Decimal.fromInt(qty);
```

**Est une doc publique (`///` Dart, `"""` Python avec contenu)**
```dart
/// Calcule le total TTC en tenant compte des remises appliquées.
Decimal get totalTtc => ...
```

**Est une licence ou en-tête de fichier**
```python
# Copyright 2024 — POS Mobile. All rights reserved.
```

**Est un TODO actionnable avec contexte**
```dart
// TODO(alice): gérer le cas où la queue est pleine (#42)
```

**Est une annotation technique nécessaire**
```dart
// ignore: avoid_dynamic_calls
// coverage:ignore-file
// dart format off
// type: ignore[attr-defined]  (Python mypy)
```

---

## WORKFLOW

### Mode standard (avec résumé)

**Étape 1 — Lire et scanner**
Identifier le langage. Scanner le fichier entier avant de modifier quoi que ce soit.

**Étape 2 — Résumé des suppressions** *(sauter en mode `--quick`)*

```
Suppressions prévues :
- 3 commentaires évidents (lignes 12, 34, 67)
- 2 blocs de code mort commenté (lignes 45-48, 89)
- 5 emojis dans les logs (lignes 23, 56, 78, 90, 102)
- 1 séparateur décoratif (ligne 5)
- 1 docstring qui répète le nom (ligne 20)

Conservés :
- doc publique /// (lignes 8, 15, 42)
- 2 TODO actionnables (lignes 30, 71)
- 1 explication non-évidente (ligne 55)
- 1 emoji UI utilisateur (ligne 88)
```

**Étape 3 — Produire le code nettoyé**
Code complet (ou diff si `--diff`). Ne pas reformater, ne pas modifier l'indentation.

**Étape 4 — Confirmation**
`X commentaires supprimés, Y emojis retirés. Logique métier intacte.`

### Mode multi-fichiers

Pour chaque fichier : afficher `### fichier.dart` en en-tête, puis résumé + confirmation.
Pas de code complet pour chaque fichier — uniquement le diff ou la liste des lignes touchées.
Résumé global à la fin : `N fichiers nettoyés — X commentaires, Y emojis retirés.`

---

## CHECKLIST AVANT DE RENDRE LE CODE

- [ ] Zéro modification de la logique métier
- [ ] Zéro import ajouté ou supprimé
- [ ] Zéro reformatage (indentation, ordre des membres)
- [ ] Doc publique `///` / docstrings utiles conservées
- [ ] TODO actionnables conservés
- [ ] Emojis UI utilisateur conservés
- [ ] Annotations lint/coverage/mypy conservées
- [ ] Pas plus de 2 lignes vides consécutives dans le résultat
