import 'dart:async';

import 'package:logger/logger.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../shared/providers/connectivity_provider.dart';
import '../../features/auth/presentation/providers/auth_providers.dart';
import '../../features/sales/presentation/providers/sales_providers.dart';
import '../../features/sync/presentation/providers/sync_providers.dart';

part 'sync_orchestrator.g.dart';

/// Sealed class representing sync orchestration states.
sealed class SyncStatus {
  const SyncStatus();
}

/// Idle state after sync completes. Optionally tracks [lastSyncAt].
class SyncStatusIdle extends SyncStatus {
  /// Creates idle state with optional last sync timestamp.
  const SyncStatusIdle({this.lastSyncAt});

  /// Timestamp of last successful sync, if any.
  final DateTime? lastSyncAt;
}

/// Syncing state while push/pull operations are in progress.
class SyncStatusSyncing extends SyncStatus {
  /// Creates syncing state.
  const SyncStatusSyncing();
}

/// Error state when sync fails.
class SyncStatusError extends SyncStatus {
  /// Creates error state with [message].
  const SyncStatusError({required this.message});

  /// User-facing error message.
  final String message;
}

/// Orchestrates bidirectional sync: monitors connectivity, triggers periodic syncs,
/// and coordinates push-before-pull sequencing to prevent data loss.
@Riverpod(keepAlive: true)
class SyncOrchestrator extends _$SyncOrchestrator {
  bool _isSyncing = false;
  Timer? _periodicTimer;
  Timer? _debounceTimer;
  final _logger = Logger();

  /// Initializes sync orchestrator with network monitoring and periodic sync.
  @override
  SyncStatus build() {
    ref.listen<AsyncValue<bool>>(isOnlineProvider, (previous, next) {
      final wasOnline = previous?.value ?? true;
      final isNowOnline = next.value ?? false;

      if (!wasOnline && isNowOnline) {
        _logger.d('Network restored, scheduling sync with 2s debounce');
        _debounceTimer?.cancel();
        _debounceTimer = Timer(const Duration(seconds: 2), syncNow);
      }
    });

    _startPeriodicSync();

    // Reset failed entries on startup to retry them (for recoverable errors like timezone bugs).
    _resetFailedEntries();

    // Initial sync on app startup (after 3s delay for app stabilization).
    Timer(const Duration(seconds: 3), () {
      final isOnlineAsync = ref.read(isOnlineProvider);
      final isOnline = isOnlineAsync.value ?? false;
      if (isOnline && !_isSyncing) {
        _logger.d('Initial sync triggered on app startup');
        unawaited(syncNow());
      }
    });

    ref.onDispose(() {
      _periodicTimer?.cancel();
      _debounceTimer?.cancel();
    });

    return const SyncStatusIdle();
  }

  /// Reset failed sync queue entries to pending so they can be retried.
  /// This helps recover from transient errors like timezone bugs that were fixed in code.
  void _resetFailedEntries() {
    unawaited(() async {
      try {
        final syncQueue = ref.read(syncQueueRepositoryProvider);
        final resetCount = await syncQueue.resetFailedEntries();
        if (resetCount > 0) {
          _logger.i('Reset $resetCount failed sync entries to pending');
        }
      } catch (e) {
        _logger.w('Failed to reset sync queue: $e');
      }
    }());
  }

  /// Starts 5-minute periodic sync timer when online.
  void _startPeriodicSync() {
    _periodicTimer = Timer.periodic(const Duration(minutes: 5), (_) {
      final isOnlineAsync = ref.read(isOnlineProvider);
      final isOnline = isOnlineAsync.value ?? false;
      if (isOnline && !_isSyncing) {
        _logger.d('Periodic sync triggered');
        unawaited(syncNow());
      }
    });
  }

  /// Orchestrates full sync: push sales, push products, then pull.
  /// Guarded against concurrent syncs (only one can run at a time).
  /// Push happens first to ensure local unsent changes are uploaded before pull.
  Future<void> syncNow() async {
    final authState = ref.read(authProvider);
    if (authState.value is! AuthAuthenticated) {
      _logger.d('Sync skipped: not authenticated');
      return;
    }

    if (_isSyncing) {
      _logger.d('Sync already in progress, ignoring concurrent request');
      return;
    }

    _isSyncing = true;
    state = const SyncStatusSyncing();

    try {
      final pushService = ref.read(pushServiceProvider);
      final pullService = ref.read(pullServiceProvider);

      _logger.d('Starting sync: push sales');
      await pushService.pushPendingSales();

      _logger.d('Sync step: push products');
      await pushService.pushPendingProductChanges();

      _logger.d('Sync step: pull changes');
      await pullService.pullChanges();

      // Invalidate sales history cache so UI refreshes with updated receipt numbers
      ref.invalidate(salesHistoryProvider);

      _logger.d('Sync completed successfully');
      state = SyncStatusIdle(lastSyncAt: DateTime.now());
    } catch (e, st) {
      _logger.e('Sync failed', error: e, stackTrace: st);
      state = const SyncStatusError(message: 'Erreur de sauvegarde');
    } finally {
      _isSyncing = false;
    }
  }
}
