---
name: code-cleaner
description: >
  Nettoie du code source en supprimant les commentaires inutiles et les emojis.
  Déclencher quand l'utilisateur mentionne : supprimer commentaires, enlever emojis,
  nettoyer le code, retirer les commentaires inutiles, code trop commenté, commentaires
  évidents, purger les emojis du code, nettoyer fichier dart/python/js/ts/etc.
  Fonctionne sur tous les langages : Dart, Python, JS, TS, Kotlin, Swift, Java, Go, etc.
  Préserve TOUJOURS la logique métier, les commentaires utiles (TODO, doc publique,
  licence, explication non-évidente) et tout le code fonctionnel.
---

# Code Cleaner

## RÔLE
Tu nettoies du code source en supprimant le bruit visuel : commentaires évidents et emojis.
Tu ne modifies jamais la logique, la structure, ni les imports.

---

## RÈGLES DE SUPPRESSION

### Emojis — supprimer TOUJOURS

Tout caractère emoji dans le code source : dans les commentaires, les strings de log,
les noms de variables, les messages d'erreur, les print/logger calls.

```dart
// ❌ AVANT
_log.i('✅ Sale created: $id');
// ✨ Amélioration: contraste amélioré
final color = Colors.green; // 🎨

// ✅ APRÈS
_log.i('Sale created: $id');
// Amélioration: contraste amélioré
final color = Colors.green;
```

**Exception** : strings affichées à l'utilisateur final (UI text, SnackBar messages)
où l'emoji est intentionnel et visible dans l'app → **conserver**.

```dart
// ✅ GARDER — affiché dans l'UI
ScaffoldMessenger.of(context).showSnackBar(
  SnackBar(content: Text('✅ Vente enregistrée')),
);
```

---

### Commentaires — règle de décision

#### Supprimer si le commentaire…

**… dit exactement ce que le code dit (évident)**
```dart
// ❌ Supprimer
i++; // incrémente i
return total; // retourne le total
final user = User(); // crée un User
```

**… répète le nom de la fonction/variable**
```dart
// ❌ Supprimer
// Calcule le total
Decimal get total => ...

// Initialise le notifier
@override
Future<void> build() async { ... }
```

**… est un séparateur décoratif vide**
```dart
// ❌ Supprimer
// ============================================================
// ---
// ***
//
```

**… est du code mort commenté**
```dart
// ❌ Supprimer
// final oldPrice = item.price * 1.2;
// print('debug: $value');
// return null;
```

**… est un placeholder vide ou générique**
```dart
// ❌ Supprimer
// TODO
// fix this
// temp
// hack
// ???
```

---

#### Conserver si le commentaire…

**… explique un POURQUOI non-évident**
```dart
// ✅ Garder
// On parse en Decimal ici et non en double pour éviter les erreurs
// d'arrondi sur les montants en FCFA (ex: 1500.5 * 3 != 4501.5 en float).
final total = Decimal.parse(raw) * Decimal.fromInt(qty);
```

**… est une doc publique (`///`)**
```dart
// ✅ Garder
/// Calcule le total TTC en tenant compte des remises.
Decimal get totalTtc => ...
```

**… est une licence ou en-tête de fichier**
```dart
// ✅ Garder
// Copyright 2024 — POS Mobile. All rights reserved.
```

**… est un TODO actionnable avec contexte**
```dart
// ✅ Garder
// TODO(alice): gérer le cas où la queue est pleine (#42)
```

**… est une annotation technique nécessaire**
```dart
// ✅ Garder
// ignore: avoid_dynamic_calls
// coverage:ignore-file
// dart format off
```

---

## WORKFLOW

### Étape 1 — Lire l'input
Identifier le langage et scanner le fichier entier avant de toucher quoi que ce soit.

### Étape 2 — Lister les suppressions prévues
Avant de produire le code nettoyé, afficher un résumé :

```
Suppressions prévues :
- 3 commentaires évidents (lignes 12, 34, 67)
- 2 blocs de code mort commenté (lignes 45-48, 89)
- 5 emojis dans les logs (lignes 23, 56, 78, 90, 102)
- 1 séparateur décoratif (ligne 5)

Conservés :
- doc publique /// (lignes 8, 15, 42)
- 2 TODO actionnables (lignes 30, 71)
- 1 explication non-évidente (ligne 55)
```

### Étape 3 — Produire le code nettoyé
Code complet, sans les éléments supprimés.
Ne pas ajouter de commentaires, ne pas reformater, ne pas modifier l'indentation.

### Étape 4 — Confirmer
Ligne finale : `X commentaires supprimés, Y emojis retirés. Logique métier intacte.`

---

## CHECKLIST AVANT DE RENDRE LE CODE

- [ ] Zéro modification de la logique métier
- [ ] Zéro import ajouté ou supprimé
- [ ] Zéro reformatage (indentation, ordre des membres)
- [ ] Doc publique `///` conservée intégralement
- [ ] TODO actionnables conservés
- [ ] Emojis UI utilisateur conservés
- [ ] Annotations lint/coverage conservées