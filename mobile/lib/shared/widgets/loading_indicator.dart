import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';

/// Consistent loading indicator widget.
///
/// Styled with the app's primary color. Used inline or full-screen.
class AppLoadingIndicator extends StatelessWidget {
  /// Creates a loading indicator.
  const AppLoadingIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox.square(
      dimension: 40,
      child: CircularProgressIndicator(
        valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
        strokeWidth: 4,
      ),
    );
  }
}

/// Full-screen loading overlay.
///
/// Blocks interaction and shows a centered spinner with optional message.
class AppLoadingScreen extends StatelessWidget {
  /// Creates a full-screen loading screen.
  const AppLoadingScreen({this.message, super.key});

  /// Optional message displayed below the spinner.
  final String? message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const AppLoadingIndicator(),
            if (message != null) ...[
              const SizedBox(height: AppSpacing.lg),
              Text(
                message!,
                style: AppTypography.bodyMedium,
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
