import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/theme/app_colors.dart';
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
    final isDisabled = onPressed == null;

    return SizedBox(
      height: 56,
      width: double.infinity,
      child: Material(
        color: isDisabled ? AppColors.inactive : AppColors.primary,
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        child: InkWell(
          onTap: isLoading || isDisabled
              ? null
              : () {
                  unawaited(HapticFeedback.lightImpact());
                  onPressed?.call();
                },
          borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
          child: Center(
            child: isLoading
                ? const SizedBox.square(
                    dimension: 24,
                    child: CircularProgressIndicator(
                      strokeWidth: 3,
                      valueColor: AlwaysStoppedAnimation<Color>(
                        AppColors.textOnPrimary,
                      ),
                    ),
                  )
                : Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (icon != null) ...[
                        Icon(icon, color: AppColors.textOnPrimary, size: 20),
                        const SizedBox(width: AppSpacing.sm),
                      ],
                      Text(
                        label,
                        style: AppTypography.labelLarge,
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}
