import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';

/// Full-width secondary action button with emerald outline.
///
/// Used for less prominent actions like Cancel or Back.
/// Minimum 56dp height for comfortable touch targets.
class SecondaryButton extends StatelessWidget {
  /// Creates a secondary button.
  const SecondaryButton({
    required this.label,
    required this.onPressed,
    this.isLoading = false,
    this.icon,
    super.key,
  });

  /// Button label text.
  final String label;

  /// Callback when button is pressed. If null, button is disabled.
  final VoidCallback? onPressed;

  /// Whether the button is in loading state.
  final bool isLoading;

  /// Optional leading icon.
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isDisabled = onPressed == null;
    final disabledColor = cs.onSurface.withValues(alpha: 0.38);
    final borderRadius = BorderRadius.circular(AppSpacing.radiusMd);

    return SizedBox(
      height: 56,
      width: double.infinity,
      child: Container(
        decoration: BoxDecoration(
          color: isDisabled ? cs.surfaceContainerHighest : cs.surface,
          borderRadius: borderRadius,
          border: Border.all(
            color: isDisabled ? cs.outlineVariant : cs.secondary,
            width: 2,
          ),
          boxShadow: isDisabled
              ? []
              : [
                  BoxShadow(
                    color: cs.secondary.withValues(alpha: 0.12),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                    spreadRadius: 0,
                  ),
                ],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: isLoading || isDisabled
                ? null
                : () {
                    unawaited(HapticFeedback.lightImpact());
                    onPressed?.call();
                  },
            borderRadius: borderRadius,
            child: Center(
              child: isLoading
                  ? SizedBox.square(
                      dimension: 24,
                      child: CircularProgressIndicator(
                        strokeWidth: 3,
                        valueColor:
                            AlwaysStoppedAnimation<Color>(cs.secondary),
                      ),
                    )
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (icon != null) ...[
                          Icon(
                            icon,
                            color: isDisabled ? disabledColor : cs.secondary,
                            size: 20,
                          ),
                          const SizedBox(width: AppSpacing.sm),
                        ],
                        Text(
                          label,
                          style: AppTypography.labelLarge.copyWith(
                            color: isDisabled ? disabledColor : cs.secondary,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
