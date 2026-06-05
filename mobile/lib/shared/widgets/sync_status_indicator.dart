import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/sync/sync_orchestrator.dart';
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
      return _buildOfflineBanner(context);
    }

    return switch (syncStatus) {
      SyncStatusSyncing() => _buildSyncingBanner(context),
      SyncStatusError(message: final msg) => _buildErrorBanner(context, msg),
      SyncStatusIdle(lastSyncAt: final lastSyncAt) =>
        pendingCount > 0
            ? _buildPendingBanner(context, pendingCount)
            : _buildIdleBanner(context, lastSyncAt != null),
    };
  }

  Widget _buildOfflineBanner(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      color: cs.tertiary,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Hors-ligne',
            style: AppTypography.labelMedium.copyWith(color: cs.onTertiary),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Vos ventes seront sauvegardées en ligne dès le retour du réseau',
            style: AppTypography.bodySmall.copyWith(color: cs.onTertiary),
          ),
        ],
      ),
    );
  }

  Widget _buildSyncingBanner(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      color: cs.primaryContainer,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(cs.primary),
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Text(
            'Sauvegarde en ligne...',
            style: AppTypography.bodySmall.copyWith(color: cs.primary),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorBanner(BuildContext context, String message) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      color: cs.errorContainer,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          Icon(Icons.warning_rounded, color: cs.error, size: 18),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              'Erreur de sauvegarde — réessayez plus tard',
              style: AppTypography.bodySmall.copyWith(color: cs.error),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPendingBanner(BuildContext context, int count) {
    final cs = Theme.of(context).colorScheme;
    final label = count == 1
        ? '1 vente à sauvegarder'
        : '$count ventes à sauvegarder';
    return Container(
      width: double.infinity,
      color: cs.tertiaryContainer,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          Icon(Icons.cloud_upload_outlined, color: cs.tertiary, size: 18),
          const SizedBox(width: AppSpacing.sm),
          Text(
            label,
            style: AppTypography.bodySmall.copyWith(color: cs.onSurface),
          ),
        ],
      ),
    );
  }

  Widget _buildIdleBanner(BuildContext context, bool hasEverSynced) {
    if (!hasEverSynced) return const SizedBox.shrink();
    final cs = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      color: cs.secondaryContainer,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.xs,
      ),
      child: Row(
        children: [
          Icon(Icons.check_circle, color: cs.secondary, size: 16),
          const SizedBox(width: AppSpacing.xs),
          Text(
            'À jour',
            style: AppTypography.captionText.copyWith(color: cs.secondary),
          ),
        ],
      ),
    );
  }
}
