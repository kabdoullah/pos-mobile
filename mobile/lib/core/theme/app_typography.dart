import 'package:flutter/material.dart';

/// Typography system for POS Mobile CI.
///
/// Scale optimized for low-literacy users, bright sunlight readability,
/// and accessibility. No custom fonts at MVP — Roboto is default Android.
/// Minimum weights w400 (normal), preferring w500–w600 for button/label clarity.
///
/// Colors are intentionally absent — applied via [ThemeData.textTheme] so that
/// light/dark mode switching works automatically. Widgets that need explicit
/// colors use `.copyWith(color: Theme.of(context).colorScheme.xxx)`.
class AppTypography {
  /// Prevent instantiation.
  AppTypography._();

  // Display scale (very large, prominent text)
  /// Large display text. 40sp, w700.
  static const TextStyle displayLarge = TextStyle(
    fontSize: 40,
    fontWeight: FontWeight.w700,
    height: 1.2,
    letterSpacing: -0.5,
  );

  /// Medium display text. 34sp, w700.
  static const TextStyle displayMedium = TextStyle(
    fontSize: 34,
    fontWeight: FontWeight.w700,
    height: 1.25,
    letterSpacing: 0,
  );

  // Headline scale (large, prominent)
  /// Large headline. 26sp, w600. AppBar titles, section headers.
  static const TextStyle titleLarge = TextStyle(
    fontSize: 26,
    fontWeight: FontWeight.w600,
    height: 1.3,
    letterSpacing: 0,
  );

  /// Medium headline. 20sp, w600. Dialog titles, list item headers.
  static const TextStyle titleMedium = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    height: 1.4,
    letterSpacing: 0.15,
  );

  // Body scale (reading text)
  /// Large body text. 18sp, w400.
  static const TextStyle bodyLarge = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.5,
  );

  /// Standard body text. 16sp, w400. **Minimum body size.**
  static const TextStyle bodyMedium = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.25,
  );

  /// Small body text. 14sp, w400. Supplementary / secondary info.
  static const TextStyle bodySmall = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.4,
  );

  // Label scale (buttons, tags, controls)
  /// Large label. 16sp, w600. Button text, CTA labels.
  static const TextStyle labelLarge = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    height: 1.4,
    letterSpacing: 0.5,
  );

  /// Medium label. 14sp, w500. Chip text, secondary button labels.
  static const TextStyle labelMedium = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.4,
    letterSpacing: 0.4,
  );

  /// Small label. 12sp, w500. Fine print, footnotes.
  static const TextStyle labelSmall = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w500,
    height: 1.4,
    letterSpacing: 0.4,
  );

  // Semantic styles — shapes only, color applied at call site via colorScheme
  /// Amount display. 34sp, w700. Large FCFA totals, transaction summaries.
  static const TextStyle amountDisplay = TextStyle(
    fontSize: 34,
    fontWeight: FontWeight.w700,
    height: 1.2,
    letterSpacing: -0.5,
  );

  /// Large amount. 28sp, w700. Line item amounts, subtotals.
  static const TextStyle amountLarge = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.w700,
    height: 1.3,
    letterSpacing: 0,
  );

  /// Caption text. 13sp, w400. Metadata, timestamps.
  static const TextStyle captionText = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    height: 1.4,
    letterSpacing: 0.4,
  );

  /// Error message style shape. Apply `colorScheme.error` at call site.
  static const TextStyle errorText = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.5,
    letterSpacing: 0.25,
  );

  /// Success message style shape. Apply `colorScheme.secondary` at call site.
  static const TextStyle successText = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.5,
    letterSpacing: 0.25,
  );

  /// Hint / placeholder text shape. Apply `colorScheme.onSurfaceVariant` at call site.
  static const TextStyle hintText = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.25,
  );
}
