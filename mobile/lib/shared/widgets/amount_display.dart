import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_typography.dart';

/// Size variants for amount display.
enum AmountSize {
  /// Small text (14sp), for line items.
  small,

  /// Medium text (18sp), for subtotals.
  medium,

  /// Large text (28sp), for total amounts.
  large,

  /// Hero text (32sp+), for prominent totals (cart, receipt).
  hero,
}

/// Formatted FCFA amount display.
///
/// Shows amounts with thousands separators (ex: "12 500 FCFA").
/// "FCFA" displayed smaller than the number for visual hierarchy.
class AmountDisplay extends StatelessWidget {
  /// Creates an amount display.
  const AmountDisplay({
    required this.amount,
    this.size = AmountSize.medium,
    this.color,
    super.key,
  });

  /// The amount to display (in FCFA).
  final Decimal amount;

  /// Size variant for the display.
  final AmountSize size;

  /// Optional text color override.
  final Color? color;

  TextStyle _getTextStyle() {
    return switch (size) {
      AmountSize.small => AppTypography.bodySmall,
      AmountSize.medium => AppTypography.bodyLarge,
      AmountSize.large => AppTypography.amountLarge,
      AmountSize.hero => AppTypography.amountDisplay,
    };
  }

  String _formatAmount() {
    final formatter = NumberFormat('#,##0', 'fr_FR');
    return formatter.format(amount.toDouble());
  }

  @override
  Widget build(BuildContext context) {
    // RichText ne propage pas DefaultTextStyle — couleur explicite obligatoire.
    final defaultColor = color ?? Theme.of(context).colorScheme.onSurface;
    final textStyle = _getTextStyle().copyWith(color: defaultColor);
    final formattedAmount = _formatAmount();

    return RichText(
      text: TextSpan(
        children: [
          TextSpan(text: formattedAmount, style: textStyle),
          TextSpan(
            text: ' FCFA',
            style: textStyle.copyWith(
              fontSize: (textStyle.fontSize ?? 16) * 0.75,
            ),
          ),
        ],
      ),
    );
  }
}
