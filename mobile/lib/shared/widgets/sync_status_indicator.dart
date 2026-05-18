import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/sync/sync_orchestrator.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../providers/connectivity_provider.dart';
import '../../features/sync/presentation/providers/sync_providers.dart';

/// Displays real-time sync status banner: offline, syncing, pending, error, or idle.
class SyncStatusIndicator extends ConsumerWidget {
  /// Creates sync status indicator.
  const SyncStatusIndicator({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnlineAsync = ref.watch(isOnlineProvider);
    final syncStatus = ref.watch(syncOrchestratorProvider);
    final pendingCountAsync = ref.watch(pendingSyncCountProvider);

    final isOnline = isOnlineAsync.value ?? false;
    final pendingCount = pendingCountAsync.value ?? 0;

    if (!isOnline) {
      return _buildOfflineBanner();
    }

    return switch (syncStatus) {
      SyncStatusSyncing() => _buildSyncingBanner(),
      SyncStatusError(message: final msg) => _buildErrorBanner(msg),
      SyncStatusIdle(lastSyncAt: final lastSyncAt) =>
        pendingCount > 0
            ? _buildPendingBanner(pendingCount)
            : _buildIdleBanner(lastSyncAt != null),
    };
  }

  Widget _buildOfflineBanner() {
    return Container(
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
    );
  }

  Widget _buildSyncingBanner() {
    return Container(
      width: double.infinity,
      color: const Color(0xFFE3F2FD),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Text(
            'Sauvegarde en ligne...',
            style: AppTypography.bodySmall.copyWith(color: AppColors.primary),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorBanner(String message) {
    return Container(
      width: double.infinity,
      color: AppColors.error.withValues(alpha: 0.1),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_rounded, color: AppColors.error, size: 18),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              'Erreur de sauvegarde — réessayez plus tard',
              style: AppTypography.bodySmall.copyWith(color: AppColors.error),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPendingBanner(int count) {
    final label = count == 1
        ? '1 vente à sauvegarder'
        : '$count ventes à sauvegarder';
    return Container(
      width: double.infinity,
      color: const Color(0xFFFFF3E0),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          const Icon(
            Icons.cloud_upload_outlined,
            color: AppColors.warning,
            size: 18,
          ),
          const SizedBox(width: AppSpacing.sm),
          Text(
            label,
            style: AppTypography.bodySmall.copyWith(
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildIdleBanner(bool hasEverSynced) {
    if (!hasEverSynced) {
      return const SizedBox.shrink();
    }
    return Container(
      width: double.infinity,
      color: const Color(0xFFE8F5E9),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.xs,
      ),
      child: Row(
        children: [
          const Icon(Icons.check_circle, color: AppColors.secondary, size: 16),
          const SizedBox(width: AppSpacing.xs),
          Text(
            'À jour',
            style: AppTypography.captionText.copyWith(
              color: AppColors.secondary,
            ),
          ),
        ],
      ),
    );
  }
}
