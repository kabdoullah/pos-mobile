import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';

/// Minimal card container with subtle elevation.
///
/// Styled after Wave's flat design. White background with
/// subtle shadow and rounded corners. Optionally tappable.
class AppCard extends StatelessWidget {
  /// Creates an app card.
  const AppCard({
    required this.child,
    this.onTap,
    this.padding = AppSpacing.md,
    super.key,
  });

  /// The card's content.
  final Widget child;

  /// Callback when card is tapped. If null, card is not tappable.
  final VoidCallback? onTap;

  /// Internal padding around the child.
  final double padding;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      elevation: onTap != null ? 1 : 0.5,
      shadowColor: AppColors.scrim,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        child: Padding(padding: EdgeInsets.all(padding), child: child),
      ),
    );
  }
}
