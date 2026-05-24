import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import 'primary_button.dart';

/// Empty state with SVG illustration.
///
/// Premium alternative to icon-only empty states. SVG illustration
/// terracotta + émeraude, title, message, optional action button.
class EmptyStateIllustrated extends StatelessWidget {
  /// Creates an empty state illustration.
  const EmptyStateIllustrated({
    required this.illustration,
    required this.title,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.illustrationSize = 180,
    super.key,
  });

  /// SVG illustration (as String, e.g., from Illustrations class).
  final String illustration;

  /// Title text.
  final String title;

  /// Descriptive message text.
  final String message;

  /// Optional action button label.
  final String? actionLabel;

  /// Callback when action button is tapped.
  final VoidCallback? onAction;

  /// Size of the illustration (width/height).
  final double illustrationSize;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox.square(
                dimension: illustrationSize,
                child: SvgPicture.string(illustration),
              ),
              const SizedBox(height: AppSpacing.xl),
              Text(
                title,
                style: AppTypography.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.md),
              Text(
                message,
                style: AppTypography.bodyMedium,
                textAlign: TextAlign.center,
              ),
              if (actionLabel != null && onAction != null) ...[
                const SizedBox(height: AppSpacing.lg),
                SizedBox(
                  width: double.infinity,
                  child: PrimaryButton(
                    label: actionLabel!,
                    onPressed: onAction,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
