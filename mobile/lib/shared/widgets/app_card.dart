import 'package:flutter/material.dart';

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
    final cs = Theme.of(context).colorScheme;
    final borderRadius = BorderRadius.circular(AppSpacing.radiusMd);
    return Container(
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: borderRadius,
        boxShadow: [
          BoxShadow(
            color: cs.shadow.withValues(alpha: 0.08),
            blurRadius: 8,
            offset: const Offset(0, 2),
            spreadRadius: 0,
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: borderRadius,
        child: InkWell(
          onTap: onTap,
          borderRadius: borderRadius,
          child: Padding(padding: EdgeInsets.all(padding), child: child),
        ),
      ),
    );
  }
}
