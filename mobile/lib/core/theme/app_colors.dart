import 'package:flutter/material.dart';

/// Complete color palette for POS Mobile CI.
///
/// All colors are semantic and named for their intended usage context.
/// Palette prioritizes accessibility (WCAG AA contrast ratios) and cultural
/// anchoring for West African merchants using the app in bright sunlight.
class AppColors {
  /// Prevent instantiation
  AppColors._();

  // Primary Terracotta (clay-earth tone, culturally anchored)
  /// Main brand color. Warm terracotta red-brick, WCAG AA 4.5:1 on white.
  /// Distinct from Orange Money (#FF6600) and MTN (#FFCC00).
  /// Usage: CTA buttons, active states, important UI elements.
  static const Color primary = Color(0xFFC1583A);

  /// Darker variant for hover/pressed states, active indicators.
  static const Color primaryDark = Color(0xFF9E3F25);

  /// Lighter tint for backgrounds, disabled states blending toward neutral.
  static const Color primaryLight = Color(0xFFE07B5F);

  /// Container background when using primary as main color accent.
  /// Used for chip backgrounds, tinted cards with primary text.
  static const Color primaryContainer = Color(0xFFFDEEE9);

  // Secondary Emerald (success, validation, positive actions)
  /// Secondary brand color. Deep emerald green, distinct from MTN yellow-green.
  /// Signals success, validation, positive confirmation, secondary CTA.
  /// Usage: Success badges, valid/verified states, secondary actions.
  static const Color secondary = Color(0xFF1A7A5E);

  /// Darker variant for secondary hover/pressed states.
  static const Color secondaryDark = Color(0xFF135C46);

  /// Lighter tint for secondary backgrounds or soft highlights.
  static const Color secondaryLight = Color(0xFF3D9E7D);

  /// Container background with secondary as accent.
  static const Color secondaryContainer = Color(0xFFE6F5F0);

  // Neutral Surface Colors (warm grays)
  /// Main app background. Slightly warm off-white, reduces eye strain
  /// in bright sunlight and long reading sessions.
  static const Color background = Color(0xFFFAF8F6);

  /// Default surface color for cards, dialogs, bottom sheets.
  /// Pure white for maximum contrast and clarity.
  static const Color surface = Color(0xFFFFFFFF);

  /// Variant surface for inactive or secondary surfaces.
  /// Used as input fill color, chip backgrounds, disabled state backgrounds.
  static const Color surfaceVariant = Color(0xFFF2EDE8);

  /// Border color for inputs, dividers, subtle UI boundaries.
  /// Warm gray for cohesion with overall palette warmth.
  static const Color border = Color(0xFFD9D0C9);

  /// Divider color for separating sections and list items.
  /// Slightly darker than border for better visibility.
  static const Color divider = Color(0xFFEDE7E1);

  // Text Colors
  /// Primary text color. Warm almost-black for maximum readability
  /// in bright light conditions. Not pure black (0xFF000000) which can be harsh.
  static const Color textPrimary = Color(0xFF1A1410);

  /// Secondary text color for labels, hints, secondary information.
  /// Warm gray with lower contrast for visual hierarchy.
  static const Color textSecondary = Color(0xFF6B5E55);

  /// Text color for disabled states or very light content.
  static const Color textDisabled = Color(0xFFB0A49D);

  /// Text color on primary-colored backgrounds.
  /// Always white for maximum contrast on terracotta.
  static const Color textOnPrimary = Color(0xFFFFFFFF);

  /// Text color on secondary-colored backgrounds.
  /// Always white for maximum contrast on emerald green.
  static const Color textOnSecondary = Color(0xFFFFFFFF);

  // Semantic Colors
  /// Error/destructive state color. Deep red, distinct from primary terracotta.
  /// Usage: Error messages, delete actions, invalid states.
  static const Color error = Color(0xFFC0392B);

  /// Background tint for error state contexts.
  static const Color errorContainer = Color(0xFFFDECEA);

  /// Success state color. Aligned with secondary emerald.
  /// Usage: Success confirmations, verified checkmarks, positive feedback.
  static const Color success = secondary; // Reuse secondary for consistency

  /// Background tint for success state contexts.
  static const Color successContainer = secondaryContainer;

  /// Warning/caution color. Warm amber, highly visible in sunlight.
  /// Usage: Warning messages, attention-needed states, time-sensitive info.
  static const Color warning = Color(0xFFD97706);

  /// Background tint for warning state contexts.
  static const Color warningContainer = Color(0xFFFEF3C7);

  // Additional Utility Colors
  /// Overlay color for modals/dialogs. Transparent dark for scrim effect.
  static const Color scrim = Color(0x991A1410);

  /// Inactive state tint (lighter than disabled text, for outlines).
  static const Color inactive = Color(0xFFE0D9D2);

  /// Dark neutral background for camera-off state overlay.
  static const Color cameraBackground = Color(0xFF1C1C1E);
}
