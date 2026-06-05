# Design System — POS Mobile

## Couleurs (valeurs exactes)

```dart
// lib/core/theme/app_colors.dart

/// Palette de couleurs du projet POS.
/// Inspiration : Wave — sobre, professionnel, mobile-first.
abstract class AppColors {
  // Primary — terracotta
  static const Color primary        = Color(0xFFC0714A);
  static const Color primaryLight   = Color(0xFFD4906D);
  static const Color primaryDark    = Color(0xFF8F5236);
  static const Color onPrimary      = Color(0xFFFFFFFF);

  // Secondary — émeraude
  static const Color secondary      = Color(0xFF2D7A5B);
  static const Color secondaryLight = Color(0xFF4A9A77);
  static const Color secondaryDark  = Color(0xFF1A5A40);
  static const Color onSecondary    = Color(0xFFFFFFFF);

  // Surfaces
  static const Color surface        = Color(0xFFFFFFFF);
  static const Color surfaceVariant = Color(0xFFF5F0ED);  // légère teinte terracotta
  static const Color background     = Color(0xFFF8F5F2);

  // Texte
  static const Color onSurface          = Color(0xFF1C1B1F);
  static const Color onSurfaceVariant   = Color(0xFF6B6066);
  static const Color outline            = Color(0xFF9E8E88);

  // États
  static const Color error    = Color(0xFFBA1A1A);
  static const Color success   = Color(0xFF2D7A5B);  // = secondary
  static const Color warning   = Color(0xFFE6A817);

  // ❌ INTERDIT — ne jamais utiliser
  // Color(0xFFFF6600) — orange Money
  // Color(0xFFFFCC00) — jaune MTN
  // Color(0xFF00A650) — vert MTN
}
```

## ThemeData complet

```dart
// lib/core/theme/app_theme.dart
import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Thème Material 3 du projet POS.
ThemeData buildAppTheme() {
  final colorScheme = ColorScheme(
    brightness: Brightness.light,
    primary: AppColors.primary,
    onPrimary: AppColors.onPrimary,
    primaryContainer: AppColors.primaryLight.withOpacity(0.2),
    onPrimaryContainer: AppColors.primaryDark,
    secondary: AppColors.secondary,
    onSecondary: AppColors.onSecondary,
    secondaryContainer: AppColors.secondaryLight.withOpacity(0.2),
    onSecondaryContainer: AppColors.secondaryDark,
    surface: AppColors.surface,
    onSurface: AppColors.onSurface,
    surfaceContainerHighest: AppColors.surfaceVariant,
    onSurfaceVariant: AppColors.onSurfaceVariant,
    outline: AppColors.outline,
    error: AppColors.error,
    onError: Colors.white,
    errorContainer: const Color(0xFFFFDAD6),
    onErrorContainer: const Color(0xFF410002),
  );

  return ThemeData(
    useMaterial3: true,
    colorScheme: colorScheme,
    fontFamily: 'Roboto', // système — pas de Google Fonts

    appBarTheme: AppBarTheme(
      centerTitle: false,
      backgroundColor: colorScheme.surface,
      foregroundColor: colorScheme.onSurface,
      elevation: 0,
      scrolledUnderElevation: 1,
    ),

    cardTheme: const CardTheme(
      elevation: 1,
      margin: EdgeInsets.zero,
    ),

    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: colorScheme.surfaceContainerHighest,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: colorScheme.primary, width: 2),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    ),

    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    ),
  );
}
```

## Tokens d'espacement

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

## Hiérarchie des boutons POS

```
FilledButton         → encaisser, valider, confirmer paiement  (1 seul par écran)
FilledButton.tonal   → action importante secondaire (ex: ajouter produit)
OutlinedButton       → annuler, retour
TextButton           → lien, action discrète
IconButton           → actions dans liste / appBar (tooltip obligatoire)
```