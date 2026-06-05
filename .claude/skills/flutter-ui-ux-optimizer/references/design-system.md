# Design System UI — POS Mobile

## Palette (valeurs exactes) — Cacao & Or

```dart
// lib/core/theme/app_colors.dart
class AppColors {
  // Primary — Brun cacao (CI #1 mondial cacao) — WCAG AA 7.1:1 on white
  static const Color primary          = Color(0xFF92400E);
  static const Color primaryDark      = Color(0xFF78350F);
  static const Color primaryLight     = Color(0xFFFB923C);
  static const Color primaryContainer = Color(0xFFFEF3C7);

  // Secondary — Or/Doré (prospérité — ≠ jaune MTN #FFCC00)
  // ⚠️  textOnSecondary MUST be dark (#1C1107) — blanc/or = 3.4:1 insuffisant WCAG AA
  static const Color secondary          = Color(0xFFCA8A04);
  static const Color secondaryDark      = Color(0xFF713F12);
  static const Color secondaryLight     = Color(0xFFFBBF24);
  static const Color secondaryContainer = Color(0xFFFEFCE8);

  // Surfaces (légèrement ivoire-chaud)
  static const Color background    = Color(0xFFFFFBF5);
  static const Color surface       = Color(0xFFFFFFFF);
  static const Color surfaceVariant = Color(0xFFFEF9EE);
  static const Color border        = Color(0xFFE7E5E4);
  static const Color divider       = Color(0xFFF5F0E8);

  // Text
  static const Color textPrimary      = Color(0xFF1C1107); // warm near-black
  static const Color textSecondary    = Color(0xFF57534E); // stone-600
  static const Color textDisabled     = Color(0xFFA8A29E); // stone-400
  static const Color textOnPrimary    = Color(0xFFFFFFFF); // blanc sur cacao 7.1:1
  static const Color textOnSecondary  = Color(0xFF1C1107); // JAMAIS blanc sur or

  // Sémantiques + containers
  static const Color error            = Color(0xFFBA1A1A);
  static const Color errorContainer   = Color(0xFFFFDAD6);
  static const Color success          = Color(0xFF166534); // vert forêt distinct du doré
  static const Color successContainer = Color(0xFFDCFCE7);
  static const Color warning          = Color(0xFFEA580C); // orange-rouge distinct du doré
  static const Color warningContainer = Color(0xFFFFEDD5);

  // Badges paiement (light/dark aware)
  static Color orangeMoneyBg(Brightness b) => b == Brightness.dark
      ? const Color(0xFF3D1A08) : const Color(0xFFFFF4ED);
  static Color mtnBg(Brightness b) => b == Brightness.dark
      ? const Color(0xFF362508) : const Color(0xFFFFFBEB);
  static Color waveBg(Brightness b) => b == Brightness.dark
      ? const Color(0xFF071830) : const Color(0xFFEFF6FF);

  // Utilitaires
  static const Color scrim            = Color(0x991C1107);
  static const Color inactive         = Color(0xFFE7E5E4);
  static const Color cameraBackground = Color(0xFF0C0906);

  // ❌ INTERDIT — jamais utiliser dans le projet POS
  // Color(0xFFFF6600) — orange Money
  // Color(0xFFFFCC00) — jaune MTN
  // Color(0xFF00A650) — vert MTN
}
```

---

## ColorScheme Material 3 (light / dark)

```dart
// lib/core/theme/app_theme.dart — AppTheme.light() / AppTheme.dark()

// LIGHT
const colorScheme = ColorScheme(
  brightness: Brightness.light,
  primary:              Color(0xFF92400E), // brun cacao — WCAG 7.1:1
  onPrimary:            Color(0xFFFFFFFF),
  primaryContainer:     Color(0xFFFEF3C7), // amber-100
  onPrimaryContainer:   Color(0xFF451A03), // brown-950
  secondary:            Color(0xFFCA8A04), // or/doré ≠ jaune MTN
  onSecondary:          Color(0xFF1C1107), // JAMAIS blanc sur or
  secondaryContainer:   Color(0xFFFEFCE8), // yellow-50
  onSecondaryContainer: Color(0xFF713F12), // amber-800
  tertiary:             Color(0xFFC2410C), // orange-rouge — warning/offline banner
  onTertiary:           Color(0xFFFFFFFF),
  tertiaryContainer:    Color(0xFFFFEDD5), // orange-100
  onTertiaryContainer:  Color(0xFF7C2D12), // orange-950
  error:                Color(0xFFBA1A1A),
  onError:              Color(0xFFFFFFFF),
  errorContainer:       Color(0xFFFFDAD6),
  onErrorContainer:     Color(0xFF410002),
  surface:              Color(0xFFFFFFFF),
  onSurface:            Color(0xFF1C1107), // warm near-black
  surfaceContainerHighest: Color(0xFFFEF9EE), // ivory-warm tint
  onSurfaceVariant:     Color(0xFF57534E), // stone-600
  outline:              Color(0xFFA8A29E), // stone-400
  outlineVariant:       Color(0xFFE7E5E4), // stone-200
  scrim:                Color(0x991C1107),
);
// scaffoldBackgroundColor: Color(0xFFFFFBF5) — ivory-warm

// DARK
const colorScheme = ColorScheme(
  brightness: Brightness.dark,
  primary:              Color(0xFFFDBA74), // amber-300 — cacao clair
  onPrimary:            Color(0xFF431407),
  primaryContainer:     Color(0xFF78350F), // amber-900
  onPrimaryContainer:   Color(0xFFFEF3C7),
  secondary:            Color(0xFFFDE68A), // amber-200 — or clair
  onSecondary:          Color(0xFF451A03),
  secondaryContainer:   Color(0xFF713F12),
  onSecondaryContainer: Color(0xFFFEFCE8),
  tertiary:             Color(0xFFFB923C), // orange-400
  onTertiary:           Color(0xFF431407),
  tertiaryContainer:    Color(0xFF7C2D12),
  onTertiaryContainer:  Color(0xFFFFEDD5),
  error:                Color(0xFFFFB4AB),
  onError:              Color(0xFF690005),
  errorContainer:       Color(0xFF93000A),
  onErrorContainer:     Color(0xFFFFDAD6),
  surface:              Color(0xFF1C1107), // near-black warm brown
  onSurface:            Color(0xFFF5F0E8), // warm white
  surfaceContainerHighest: Color(0xFF3D2A14),
  onSurfaceVariant:     Color(0xFFD6C7B8),
  outline:              Color(0xFF9D8E81),
  outlineVariant:       Color(0xFF4A3728),
  scrim:                Color(0x990C0906),
);
// scaffoldBackgroundColor: Color(0xFF0C0906) — near-black warm cacao
```

## ThemeData — composants configurés

`AppTheme.light()` / `AppTheme.dark()` configure automatiquement :
- `appBarTheme` — surface bg, elevation 0, scrolledUnderElevation 1
- `cardTheme` — elevation 0, radius `AppSpacing.radiusLg`
- `inputDecorationTheme` — filled, outline borders 4 états (enabled/focused/error/disabled)
- `elevatedButtonTheme` — primary bg, height `AppSpacing.buttonHeight`, radius md
- `outlinedButtonTheme` — primary stroke width 2, height `AppSpacing.buttonHeight`
- `textButtonTheme` — primary color
- `chipTheme` — surfaceContainer bg, primaryContainer selected
- `dividerTheme` — outlineVariant, thickness 1
- `snackBarTheme` — floating, onSurface bg, primary action
- `bottomNavigationBarTheme` — fixed, primary selected
- `floatingActionButtonTheme` — primary, elevation 0, radius sm
- `progressIndicatorTheme` — primary, surfaceContainer track
- `switchTheme` / `checkboxTheme` — primary when selected

---

## Hiérarchie des boutons POS

```
FilledButton           → encaisser, valider, confirmer paiement  (1 seul par écran)
FilledButton.tonal     → ajouter produit, action secondaire importante
OutlinedButton         → annuler, modifier
TextButton             → liens, actions discrètes
IconButton + tooltip   → actions dans liste ou AppBar
```

---

## Tokens d'espacement (grille 4dp)

```dart
abstract class AppSpacing {
  static const double xs  = 4;
  static const double sm  = 8;
  static const double md  = 16;
  static const double lg  = 24;
  static const double xl  = 32;
  static const double xxl = 48;
}
```

---

## Animations (Motion Design POS)

```dart
// ✅ Apparition d'éléments
AnimatedOpacity(duration: Duration(milliseconds: 200), opacity: visible ? 1 : 0, child: ...)

// ✅ Changement de contenu (loading → data)
AnimatedSwitcher(duration: Duration(milliseconds: 300), child: ...)

// ✅ Transition de taille (panier)
AnimatedContainer(duration: Duration(milliseconds: 250), curve: Curves.easeInOut, ...)

// ❌ Éviter
// Durées > 400ms (ressenti lent sur POS en usage intensif)
// Curves.bounceOut (non professionnel)
// Animations non interruptibles
```

---

## Widgets core/ réutilisables

Ces widgets existent dans `lib/core/widgets/` — les utiliser, ne pas les recréer :

| Widget | Usage |
|--------|-------|
| `EmptyState` | Listes vides (icon + titre + subtitle + action optionnelle) |
| `AmountDisplay` | Affichage d'un `Decimal` formaté avec devise |
| `LoadingOverlay` | Overlay de chargement sur un écran |
| `AppErrorWidget` | Erreur avec bouton "Réessayer" |