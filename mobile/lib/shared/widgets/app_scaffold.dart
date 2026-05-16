import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../providers/connectivity_provider.dart';

/// Standard app scaffold with optional offline banner.
///
/// Displays a yellow warning banner when offline to notify users
/// that their actions will be synced when connectivity returns.
class AppScaffold extends ConsumerWidget {
  /// Creates an app scaffold.
  const AppScaffold({
    required this.title,
    required this.body,
    this.actions,
    this.floatingActionButton,
    this.showOfflineBanner = true,
    super.key,
  });

  /// AppBar title.
  final String title;

  /// Main content of the scaffold.
  final Widget body;

  /// Actions to display in the AppBar.
  final List<Widget>? actions;

  /// Floating action button widget.
  final Widget? floatingActionButton;

  /// Whether to show offline banner when disconnected.
  final bool showOfflineBanner;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnline = ref.watch(connectivityStatusProvider);

    return Scaffold(
      appBar: AppBar(title: Text(title), actions: actions),
      body: Column(
        children: [
          if (showOfflineBanner && !isOnline)
            Container(
              width: double.infinity,
              color: AppColors.warning,
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Hors-ligne',
                    style: AppTypography.labelMedium.copyWith(
                      color: AppColors.textPrimary,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Vos ventes seront sauvegardées en ligne dès le retour du réseau',
                    style: AppTypography.bodySmall.copyWith(
                      color: AppColors.textPrimary,
                    ),
                  ),
                ],
              ),
            ),
          Expanded(child: body),
        ],
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}
