import 'dart:async';

import 'package:logger/logger.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../shared/providers/connectivity_provider.dart';
import '../../features/sync/presentation/providers/sync_providers.dart';

part 'sync_orchestrator.g.dart';

sealed class SyncStatus {
  const SyncStatus();
}

class SyncStatusIdle extends SyncStatus {
  const SyncStatusIdle({this.lastSyncAt});

  final DateTime? lastSyncAt;
}

class SyncStatusSyncing extends SyncStatus {
  const SyncStatusSyncing();
}

class SyncStatusError extends SyncStatus {
  const SyncStatusError({required this.message});

  final String message;
}

@Riverpod(keepAlive: true)
class SyncOrchestrator extends _$SyncOrchestrator {
  bool _isSyncing = false;
  Timer? _periodicTimer;
  Timer? _debounceTimer;
  final _logger = Logger();

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

    ref.onDispose(() {
      _periodicTimer?.cancel();
      _debounceTimer?.cancel();
    });

    return const SyncStatusIdle();
  }

  void _startPeriodicSync() {
    _periodicTimer = Timer.periodic(const Duration(minutes: 5), (_) {
      final isOnlineAsync = ref.read(isOnlineProvider);
      final isOnline = isOnlineAsync.value ?? false;
      if (isOnline && !_isSyncing) {
        _logger.d('Periodic sync triggered');
        syncNow();
      }
    });
  }

  /// Orchestrates full sync: push sales, push products, then pull.
  /// Guarded against concurrent syncs (only one can run at a time).
  /// Push happens first to ensure local unsent changes are uploaded before pull.
  Future<void> syncNow() async {
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

      _logger.d('Sync completed successfully');
      state = SyncStatusIdle(lastSyncAt: DateTime.now());
    } catch (e, st) {
      _logger.e('Sync failed', error: e, stackTrace: st);
      state = SyncStatusError(message: 'Erreur de sauvegarde');
    } finally {
      _isSyncing = false;
    }
  }
}
