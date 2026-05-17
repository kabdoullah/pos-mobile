import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:mobile/core/sync/pull_service.dart';
import 'package:mobile/core/sync/push_service.dart';
import 'package:mobile/core/sync/sync_orchestrator.dart';
import 'package:mobile/features/sync/data/datasources/sync_remote_datasource.dart';
import 'package:mobile/features/sync/presentation/providers/sync_providers.dart';
import 'package:mobile/shared/providers/connectivity_provider.dart';

class MockPushService extends Mock implements PushService {}

class MockPullService extends Mock implements PullService {}

class MockSyncRemoteDataSource extends Mock implements SyncRemoteDataSource {}

void main() {
  group('SyncOrchestrator', () {
    late MockPushService mockPushService;
    late MockPullService mockPullService;

    setUp(() {
      mockPushService = MockPushService();
      mockPullService = MockPullService();

      when(
        () => mockPushService.pushPendingSales(),
      ).thenAnswer((_) async => {});
      when(
        () => mockPushService.pushPendingProductChanges(),
      ).thenAnswer((_) async => {});
      when(() => mockPullService.pullChanges()).thenAnswer((_) async => true);
    });

    test('syncNow when called twice concurrently ignores second call', () async {
      final container = ProviderContainer(
        overrides: [
          pushServiceProvider.overrideWithValue(mockPushService),
          pullServiceProvider.overrideWithValue(mockPullService),
          isOnlineProvider.overrideWith(
            (_) => Stream.value(true).asBroadcastStream(),
          ),
        ],
      );
      addTearDown(container.dispose);

      when(
        () => mockPushService.pushPendingSales(),
      ).thenAnswer((_) => Future.delayed(const Duration(milliseconds: 100)));

      final orchestrator = container.read(syncOrchestratorProvider.notifier);

      // Call syncNow twice without awaiting
      unawaited(orchestrator.syncNow());
      unawaited(orchestrator.syncNow());

      // Wait for first sync to complete
      await Future.delayed(const Duration(milliseconds: 200));

      // Verify pushPendingSales was called only once (second call was ignored)
      verify(() => mockPushService.pushPendingSales()).called(1);
    });

    test(
      'syncNow calls push before pull (push sales, products, then pull)',
      () async {
        final callOrder = <String>[];

        when(() => mockPushService.pushPendingSales()).thenAnswer((_) async {
          callOrder.add('pushSales');
        });
        when(() => mockPushService.pushPendingProductChanges()).thenAnswer((
          _,
        ) async {
          callOrder.add('pushProducts');
        });
        when(() => mockPullService.pullChanges()).thenAnswer((_) async {
          callOrder.add('pull');
          return true;
        });

        final container = ProviderContainer(
          overrides: [
            pushServiceProvider.overrideWithValue(mockPushService),
            pullServiceProvider.overrideWithValue(mockPullService),
            isOnlineProvider.overrideWith(
              (_) => Stream.value(true).asBroadcastStream(),
            ),
          ],
        );
        addTearDown(container.dispose);

        final orchestrator = container.read(syncOrchestratorProvider.notifier);
        await orchestrator.syncNow();

        expect(callOrder, equals(['pushSales', 'pushProducts', 'pull']));
      },
    );

    // Test for connectivity-triggered sync is omitted due to complex
    // timing with ref.listen in build(). Manual testing confirms debounce
    // works as intended (see adr/0005-sync-hybrid.md).

    test(
      'syncNow updates state to SyncStatusSyncing then SyncStatusIdle',
      () async {
        // Override mocks with delay to ensure we see the syncing state
        when(
          () => mockPushService.pushPendingSales(),
        ).thenAnswer((_) => Future.delayed(const Duration(milliseconds: 300)));

        final container = ProviderContainer(
          overrides: [
            pushServiceProvider.overrideWithValue(mockPushService),
            pullServiceProvider.overrideWithValue(mockPullService),
            isOnlineProvider.overrideWith(
              (_) => Stream.value(true).asBroadcastStream(),
            ),
          ],
        );
        addTearDown(container.dispose);

        final orchestrator = container.read(syncOrchestratorProvider.notifier);

        // Initially idle
        expect(container.read(syncOrchestratorProvider), isA<SyncStatusIdle>());

        // Call syncNow (but don't await immediately)
        final syncFuture = orchestrator.syncNow();
        await Future.delayed(const Duration(milliseconds: 50));

        // Should be syncing
        expect(
          container.read(syncOrchestratorProvider),
          isA<SyncStatusSyncing>(),
        );

        // Wait for completion
        await syncFuture;

        // Should be idle again with lastSyncAt set
        final finalState = container.read(syncOrchestratorProvider);
        expect(finalState, isA<SyncStatusIdle>());
        expect((finalState as SyncStatusIdle).lastSyncAt, isNotNull);
      },
    );

    test('syncNow on error sets SyncStatusError', () async {
      final errorMockPushService = MockPushService();
      when(
        () => errorMockPushService.pushPendingSales(),
      ).thenThrow(Exception('Network error'));
      when(
        () => errorMockPushService.pushPendingProductChanges(),
      ).thenAnswer((_) async => {});

      final container = ProviderContainer(
        overrides: [
          pushServiceProvider.overrideWithValue(errorMockPushService),
          pullServiceProvider.overrideWithValue(mockPullService),
          isOnlineProvider.overrideWith(
            (_) => Stream.value(true).asBroadcastStream(),
          ),
        ],
      );
      addTearDown(container.dispose);

      final orchestrator = container.read(syncOrchestratorProvider.notifier);
      await orchestrator.syncNow();

      final state = container.read(syncOrchestratorProvider);
      expect(state, isA<SyncStatusError>());
    });
  });
}
