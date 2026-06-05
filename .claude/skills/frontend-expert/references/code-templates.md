# Templates de code — POS Mobile

## Entité domain (freezed)

```dart
// lib/features/sale/domain/entities/sale.dart
import 'package:decimal/decimal.dart';
import 'package:freezed_annotation/freezed_annotation.dart';

part 'sale.freezed.dart';

/// Entité métier représentant une vente.
@freezed
class Sale with _$Sale {
  const factory Sale({
    required String id,
    required List<SaleItem> items,
    required Decimal total,        // ← Decimal, JAMAIS double
    required DateTime createdAt,
    required SaleStatus status,
  }) = _Sale;
}

enum SaleStatus { pending, synced, failed }
```

## DTO + Mapper (data/)

```dart
// lib/features/sale/data/models/sale_dto.dart
import 'package:freezed_annotation/freezed_annotation.dart';

part 'sale_dto.freezed.dart';
part 'sale_dto.g.dart';

@freezed
class SaleDto with _$SaleDto {
  const factory SaleDto({
    required String id,
    required String total,        // ← String en transport réseau
    @JsonKey(name: 'created_at') required String createdAt,
  }) = _SaleDto;

  factory SaleDto.fromJson(Map<String, dynamic> json) =>
      _$SaleDtoFromJson(json);
}

// lib/features/sale/data/models/sale_dto.mapper.dart
import 'package:decimal/decimal.dart';
import '../../domain/entities/sale.dart';
import 'sale_dto.dart';

extension SaleDtoMapper on SaleDto {
  Sale toDomain() => Sale(
    id: id,
    total: Decimal.parse(total),   // ← conversion String→Decimal ici
    createdAt: DateTime.parse(createdAt),
    items: [],
    status: SaleStatus.synced,
  );
}

extension SaleMapper on Sale {
  SaleDto toDto() => SaleDto(
    id: id,
    total: total.toString(),        // ← conversion Decimal→String ici
    createdAt: createdAt.toIso8601String(),
  );
}
```

## Interface Repository (domain/)

```dart
// lib/features/sale/domain/repositories/i_sale_repository.dart

/// Interface du repository des ventes.
/// Implémentée dans data/, injectée via providers/.
abstract interface class ISaleRepository {
  /// Retourne toutes les ventes depuis le cache local.
  Future<List<Sale>> getAll();

  /// Crée une vente localement et l'enqueue pour synchronisation.
  Future<void> create(Sale sale);

  /// Écoute les changements en temps réel (drift stream).
  Stream<List<Sale>> watchAll();
}
```

## Repository Impl (data/) — offline-first

```dart
// lib/features/sale/data/repositories/sale_repository_impl.dart
import 'package:logger/logger.dart';
import '../../domain/entities/sale.dart';
import '../../domain/repositories/i_sale_repository.dart';
import '../datasources/sale_local_datasource.dart';
import '../../../../core/sync/sync_queue.dart';

/// Implémentation offline-first du repository des ventes.
class SaleRepositoryImpl implements ISaleRepository {
  const SaleRepositoryImpl(this._local, this._syncQueue);

  final SaleLocalDatasource _local;
  final SyncQueue _syncQueue;
  final _log = Logger('SaleRepositoryImpl');

  @override
  Future<List<Sale>> getAll() => _local.findAll();

  @override
  Stream<List<Sale>> watchAll() => _local.watchAll();

  @override
  Future<void> create(Sale sale) async {
    await _local.insert(sale);
    await _syncQueue.enqueue(SyncTask.createSale(sale.id));
    _log.i('Sale ${sale.id} created and enqueued for sync');
  }
}
```

## AsyncNotifier (presentation/)

```dart
// lib/features/sale/presentation/notifiers/sale_notifier.dart
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../domain/entities/sale.dart';
import '../../domain/repositories/i_sale_repository.dart';

part 'sale_notifier.g.dart';

/// Notifier gérant l'état de la liste des ventes.
@riverpod
class SaleNotifier extends _$SaleNotifier {
  late ISaleRepository _repository;

  @override
  Future<List<Sale>> build() async {
    _repository = ref.read(saleRepositoryProvider);
    return _repository.getAll();
  }

  /// Crée une nouvelle vente.
  Future<void> create(Sale sale) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      await _repository.create(sale);
      return _repository.getAll();
    });
  }
}
```

## Providers (providers/)

```dart
// lib/features/sale/providers/sale_providers.dart
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../data/datasources/sale_local_datasource.dart';
import '../data/datasources/sale_remote_datasource.dart';
import '../data/repositories/sale_repository_impl.dart';
import '../domain/repositories/i_sale_repository.dart';
import '../../../core/database/app_database.dart';
import '../../../core/network/dio_client.dart';
import '../../../core/sync/sync_queue.dart';

part 'sale_providers.g.dart';

@riverpod
SaleLocalDatasource saleLocalDatasource(Ref ref) =>
    SaleLocalDatasource(ref.read(appDatabaseProvider));

@riverpod
SaleRemoteDatasource saleRemoteDatasource(Ref ref) =>
    SaleRemoteDatasource(ref.read(dioClientProvider));

@riverpod
ISaleRepository saleRepository(Ref ref) => SaleRepositoryImpl(
  ref.read(saleLocalDatasourceProvider),
  ref.read(syncQueueProvider),
);
```

## Screen avec états (presentation/)

```dart
// lib/features/sale/presentation/screens/sale_screen.dart
import 'package:flutter/material.dart';
import 'package:hooks_riverpod/hooks_riverpod.dart';
import '../notifiers/sale_notifier.dart';
import '../../../../core/widgets/empty_state.dart';

/// Écran principal listant les ventes.
class SaleScreen extends ConsumerWidget {
  const SaleScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final salesAsync = ref.watch(saleNotifierProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Ventes')),
      body: salesAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Erreur : $e'),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () => ref.invalidate(saleNotifierProvider),
                child: const Text('Réessayer'),
              ),
            ],
          ),
        ),
        data: (sales) => sales.isEmpty
            ? const EmptyState(
                icon: Icons.receipt_long_outlined,
                title: 'Aucune vente',
                subtitle: 'Les ventes apparaîtront ici.',
              )
            : ListView.builder(
                itemCount: sales.length,
                itemBuilder: (context, i) => _SaleTile(sale: sales[i]),
              ),
      ),
    );
  }
}
```

## AmountDisplay widget (core/)

```dart
// lib/core/widgets/amount_display.dart
import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';

/// Affiche un montant monétaire formaté.
/// Toujours utiliser ce widget, jamais amount.toString() direct.
class AmountDisplay extends StatelessWidget {
  const AmountDisplay({
    super.key,
    required this.amount,
    this.currency = 'FCFA',
    this.style,
  });

  final Decimal amount;
  final String currency;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    return Text(
      '${_format(amount)} $currency',
      style: style ?? Theme.of(context).textTheme.bodyMedium,
    );
  }

  String _format(Decimal value) =>
      value.toStringAsFixed(0).replaceAllMapped(
        RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
        (m) => '${m[1]} ',
      );
}
```