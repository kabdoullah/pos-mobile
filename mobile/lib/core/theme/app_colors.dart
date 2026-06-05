import 'package:flutter/material.dart';

/// Light-mode color palette — Cacao & Or.
///
/// Primary: brun cacao profond (`#92400E`) — autorité, premium, Côte d'Ivoire
/// (#1 mondial cacao). Secondary: or/doré (`#CA8A04`) — prospérité, succès.
///
/// **Règle critique :** [textOnSecondary] est sombre (`#1C1107`), jamais blanc
/// sur or (contraste blanc/`#CA8A04` = 3.4:1 — insuffisant WCAG AA body text).
///
/// For dark-mode counterparts and stock status colors, use [AppSemanticColors]
/// via `Theme.of(context).extension<AppSemanticColors>()!`.
class AppColors {
  /// Prevent instantiation.
  AppColors._();

  // Primary — Brun cacao (Côte d'Ivoire #1 mondial cacao)
  /// Main brand color. WCAG AA 7.1:1 on white.
  static const Color primary = Color(0xFF92400E);

  /// Darker variant for pressed/active states.
  static const Color primaryDark = Color(0xFF78350F);

  /// Lighter tint for hover states and dark-mode primary.
  static const Color primaryLight = Color(0xFFFB923C);

  /// Container background with primary as accent.
  static const Color primaryContainer = Color(0xFFFEF3C7);

  // Secondary — Or/Doré (prospérité — ≠ jaune MTN #FFCC00)
  /// Secondary brand color. Gold accent for success and highlights.
  static const Color secondary = Color(0xFFCA8A04);

  /// Darker variant for secondary pressed states.
  static const Color secondaryDark = Color(0xFF713F12);

  /// Lighter tint for secondary highlights.
  static const Color secondaryLight = Color(0xFFFBBF24);

  /// Container background with secondary as accent.
  static const Color secondaryContainer = Color(0xFFFEFCE8);

  // Neutral Surfaces (légèrement ivoire-chaud)
  /// Main app background. Warm ivory tint, reduces eye strain.
  static const Color background = Color(0xFFFFFBF5);

  /// Default surface for cards, dialogs, bottom sheets.
  static const Color surface = Color(0xFFFFFFFF);

  /// Variant surface for input fills, chip backgrounds.
  static const Color surfaceVariant = Color(0xFFFEF9EE);

  /// Border color for inputs and UI boundaries.
  static const Color border = Color(0xFFE7E5E4);

  /// Divider color for section separators.
  static const Color divider = Color(0xFFF5F0E8);

  // Text Colors
  /// Primary text. Warm near-black — max readability on ivory surfaces.
  static const Color textPrimary = Color(0xFF1C1107);

  /// Secondary text for references, locations, secondary labels.
  static const Color textSecondary = Color(0xFF57534E);

  /// Disabled/placeholder text.
  static const Color textDisabled = Color(0xFFA8A29E);

  /// Text on primary-colored backgrounds (always white — cacao 7.1:1 on white).
  static const Color textOnPrimary = Color(0xFFFFFFFF);

  /// Text on secondary-colored backgrounds.
  ///
  /// **Must be dark** — white on gold `#CA8A04` = 3.4:1 (fails WCAG AA body).
  static const Color textOnSecondary = Color(0xFF1C1107);

  // Semantic Colors
  /// Error / stock rupture. WCAG AA on white.
  static const Color error = Color(0xFFBA1A1A);

  /// Background tint for error state containers.
  static const Color errorContainer = Color(0xFFFFDAD6);

  /// Success state. Forest green — distinct from secondary gold.
  static const Color success = Color(0xFF166534);

  /// Background tint for success state containers.
  static const Color successContainer = Color(0xFFDCFCE7);

  /// Warning / stock low / reorder needed.
  ///
  /// Orange-red — visually distinct from secondary gold `#CA8A04`.
  static const Color warning = Color(0xFFEA580C);

  /// Background tint for warning state containers.
  static const Color warningContainer = Color(0xFFFFEDD5);

  // Payment badge backgrounds — couleurs brand tierces, light/dark aware
  /// Orange Money badge background.
  static Color orangeMoneyBg(Brightness b) => b == Brightness.dark
      ? const Color(0xFF3D1A08)
      : const Color(0xFFFFF4ED);

  /// MTN Mobile Money badge background.
  static Color mtnBg(Brightness b) => b == Brightness.dark
      ? const Color(0xFF362508)
      : const Color(0xFFFFFBEB);

  /// Wave badge background.
  static Color waveBg(Brightness b) => b == Brightness.dark
      ? const Color(0xFF071830)
      : const Color(0xFFEFF6FF);

  // Utility
  /// Scrim for modals and overlays.
  static const Color scrim = Color(0x991C1107);

  /// Inactive state outline color.
  static const Color inactive = Color(0xFFE7E5E4);

  /// Dark background for camera-off overlay.
  static const Color cameraBackground = Color(0xFF0C0906);
}
