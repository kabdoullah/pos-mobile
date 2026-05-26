import 'package:flutter/material.dart';

/// Light-mode color palette for POS Mobile CI.
///
/// SaaS-modern palette optimized for stock management: high contrast,
/// clear semantic status colors (critical/low/ok), distinct from
/// Orange Money (#FF6600) and MTN (#FFCC00) brand colors.
///
/// For dark-mode counterparts and stock status colors, use [AppSemanticColors]
/// via `Theme.of(context).extension<AppSemanticColors>()!`.
class AppColors {
  /// Prevent instantiation.
  AppColors._();

  // Primary — Electric Blue (SaaS CTA, scan, validate)
  /// Main brand color. WCAG AA 4.5:1 on white.
  static const Color primary = Color(0xFF2563EB);

  /// Darker variant for pressed/active states.
  static const Color primaryDark = Color(0xFF1D4ED8);

  /// Lighter tint for hover states.
  static const Color primaryLight = Color(0xFF3B82F6);

  /// Container background with primary as accent.
  static const Color primaryContainer = Color(0xFFDBEAFE);

  // Secondary — Emerald Green (stock OK / success)
  /// Secondary brand color. Stock available, positive confirmation.
  static const Color secondary = Color(0xFF16A34A);

  /// Darker variant for secondary pressed states.
  static const Color secondaryDark = Color(0xFF15803D);

  /// Lighter tint for secondary highlights.
  static const Color secondaryLight = Color(0xFF22C55E);

  /// Container background with secondary as accent.
  static const Color secondaryContainer = Color(0xFFDCFCE7);

  // Neutral Surfaces
  /// Main app background. Avoids glare in warehouse environments.
  static const Color background = Color(0xFFF8FAFC);

  /// Default surface for cards, dialogs, bottom sheets.
  static const Color surface = Color(0xFFFFFFFF);

  /// Variant surface for input fills, chip backgrounds.
  static const Color surfaceVariant = Color(0xFFF1F5F9);

  /// Border color for inputs and UI boundaries.
  static const Color border = Color(0xFFE2E8F0);

  /// Divider color for section separators.
  static const Color divider = Color(0xFFF1F5F9);

  // Text Colors
  /// Primary text. Maximum readability for stock quantities and amounts.
  static const Color textPrimary = Color(0xFF0F172A);

  /// Secondary text for SKU references, locations, secondary labels.
  static const Color textSecondary = Color(0xFF475569);

  /// Disabled/placeholder text.
  static const Color textDisabled = Color(0xFF94A3B8);

  /// Text on primary-colored backgrounds (always white).
  static const Color textOnPrimary = Color(0xFFFFFFFF);

  /// Text on secondary-colored backgrounds (always white).
  static const Color textOnSecondary = Color(0xFFFFFFFF);

  // Semantic Colors
  /// Error / stock rupture. Distinct from primary blue.
  static const Color error = Color(0xFFDC2626);

  /// Background tint for error state containers.
  static const Color errorContainer = Color(0xFFFEE2E2);

  /// Success state. Aligned with secondary emerald.
  static const Color success = secondary;

  /// Background tint for success state containers.
  static const Color successContainer = secondaryContainer;

  /// Warning / stock low / reorder needed.
  static const Color warning = Color(0xFFD97706);

  /// Background tint for warning state containers.
  static const Color warningContainer = Color(0xFFFEF3C7);

  // Utility
  /// Scrim for modals and overlays.
  static const Color scrim = Color(0x990F172A);

  /// Inactive state outline color.
  static const Color inactive = Color(0xFFE2E8F0);

  /// Dark background for camera-off overlay.
  static const Color cameraBackground = Color(0xFF0B0F19);
}
