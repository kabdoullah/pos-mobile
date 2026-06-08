import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';

/// Full-width primary action button with terracotta branding.
///
/// Designed for accessibility and mobile-first UX. Minimum 56dp height
/// for comfortable touch targets. Supports loading and disabled states.
class PrimaryButton extends StatelessWidget {
  /// Creates a primary button.
  const PrimaryButton({
    required this.label,
    required this.onPressed,
    this.isLoading = false,
    this.icon,
    this.trailingIcon,
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

  /// Optional trailing icon (e.g. arrow for directional CTAs).
  final IconData? trailingIcon;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isDisabled = onPressed == null;
    final borderRadius = BorderRadius.circular(AppSpacing.radiusMd);

    return SizedBox(
      height: 56,
      width: double.infinity,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: borderRadius,
          boxShadow: isDisabled
              ? []
              : [
                  BoxShadow(
                    color: cs.primary.withValues(alpha: 0.25),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                    spreadRadius: 0,
                  ),
                ],
        ),
        child: Material(
          color: isDisabled ? cs.onSurface.withValues(alpha: 0.12) : cs.primary,
          borderRadius: borderRadius,
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
                        valueColor: AlwaysStoppedAnimation<Color>(cs.onPrimary),
                      ),
                    )
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (icon != null) ...[
                          Icon(icon, color: cs.onPrimary, size: 20),
                          const SizedBox(width: AppSpacing.sm),
                        ],
                        Text(
                          label,
                          style: AppTypography.labelLarge.copyWith(
                            color: cs.onPrimary,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        if (trailingIcon != null) ...[
                          const SizedBox(width: AppSpacing.sm),
                          Icon(trailingIcon, color: cs.onPrimary, size: 20),
                        ],
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
