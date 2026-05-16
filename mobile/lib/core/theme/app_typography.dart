import 'package:flutter/material.dart';
import 'app_colors.dart';

/// Typography system for POS Mobile CI.
///
/// Scale optimized for low-literacy users, bright sunlight readability,
/// and accessibility. No custom fonts at MVP — Roboto is default Android.
/// Minimum weights w400 (normal), preferring w500–w600 for button/label clarity.
class AppTypography {
  /// Prevent instantiation
  AppTypography._();

  // Display scale (very large, prominent text)
  /// Large display text. 40sp, w700.
  /// Usage: empty state illustrations, onboarding titles, section headers.
  static const TextStyle displayLarge = TextStyle(
    fontSize: 40,
    fontWeight: FontWeight.w700,
    height: 1.2,
    letterSpacing: -0.5,
    color: AppColors.textPrimary,
  );

  /// Medium display text. 34sp, w700.
  /// Usage: large screen titles, prominent messages.
  static const TextStyle displayMedium = TextStyle(
    fontSize: 34,
    fontWeight: FontWeight.w700,
    height: 1.25,
    letterSpacing: 0,
    color: AppColors.textPrimary,
  );

  // Headline scale (large, prominent)
  /// Large headline. 26sp, w600.
  /// Usage: AppBar titles, main section headers, card titles.
  static const TextStyle titleLarge = TextStyle(
    fontSize: 26,
    fontWeight: FontWeight.w600,
    height: 1.3,
    letterSpacing: 0,
    color: AppColors.textPrimary,
  );

  /// Medium headline. 20sp, w600.
  /// Usage: subsection headers, dialog titles, list item headers.
  static const TextStyle titleMedium = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w600,
    height: 1.4,
    letterSpacing: 0.15,
    color: AppColors.textPrimary,
  );

  // Body scale (reading text)
  /// Large body text. 18sp, w400.
  /// Usage: prominent content, introductory paragraphs.
  static const TextStyle bodyLarge = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.5,
    color: AppColors.textPrimary,
  );

  /// Standard body text. 16sp, w400. **MINIMUM body size.**
  /// Usage: standard paragraph text, list item descriptions, general content.
  static const TextStyle bodyMedium = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.25,
    color: AppColors.textPrimary,
  );

  /// Small body text. 14sp, w400.
  /// Usage: supplementary text, secondary info, additional details.
  static const TextStyle bodySmall = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.4,
    color: AppColors.textSecondary,
  );

  // Label scale (buttons, tags, controls)
  /// Large label. 16sp, w600.
  /// Usage: button text, CTA labels, important badges.
  static const TextStyle labelLarge = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    height: 1.4,
    letterSpacing: 0.5,
    color: AppColors.textOnPrimary,
  );

  /// Medium label. 14sp, w500.
  /// Usage: chip text, secondary button labels, medium-importance tags.
  static const TextStyle labelMedium = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.4,
    letterSpacing: 0.4,
    color: AppColors.textPrimary,
  );

  /// Small label. 12sp, w500.
  /// Usage: fine print, footnotes, minimal-importance chips. Avoid except where necessary.
  static const TextStyle labelSmall = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w500,
    height: 1.4,
    letterSpacing: 0.4,
    color: AppColors.textSecondary,
  );

  // Semantic styles (amounts, special cases)
  /// Amount display. 34sp, w700.
  /// Usage: large price/balance amounts, FCFA totals, transaction summaries.
  /// Extra visibility for financial numbers in daily POS workflow.
  static const TextStyle amountDisplay = TextStyle(
    fontSize: 34,
    fontWeight: FontWeight.w700,
    height: 1.2,
    letterSpacing: -0.5,
    color: AppColors.textPrimary,
  );

  /// Large amount. 28sp, w700.
  /// Usage: line item amounts, subtotals, secondary price displays.
  static const TextStyle amountLarge = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.w700,
    height: 1.3,
    letterSpacing: 0,
    color: AppColors.textPrimary,
  );

  /// Caption text. 13sp, w400.
  /// Usage: image captions, metadata, timestamps, very light text.
  static const TextStyle captionText = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    height: 1.4,
    letterSpacing: 0.4,
    color: AppColors.textSecondary,
  );

  // Helper styles for common cases
  /// Error message style. Red, bodyMedium size.
  static const TextStyle errorText = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.5,
    letterSpacing: 0.25,
    color: AppColors.error,
  );

  /// Success message style. Green, bodyMedium size.
  static const TextStyle successText = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.5,
    letterSpacing: 0.25,
    color: AppColors.success,
  );

  /// Hint/placeholder text. Secondary color, slightly smaller.
  static const TextStyle hintText = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    height: 1.5,
    letterSpacing: 0.25,
    color: AppColors.textSecondary,
  );
}
