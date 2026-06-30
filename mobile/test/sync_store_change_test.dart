import 'dart:ffi';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/sync/local_data_reset_service.dart';
import 'package:mobile/core/sync/pull_service.dart';
import 'package:mobile/database/app_database.dart';
import 'package:sqlite3/open.dart';

void main() {
  late AppDatabase db;

  setUpAll(() {
    // Le host Linux expose libsqlite3.so.0 ; drift cherche libsqlite3.so.
    if (Platform.isLinux) {
      open.overrideFor(
        OperatingSystem.linux,
        () => DynamicLibrary.open('libsqlite3.so.0'),
      );
    }
  });

  setUp(() {
    db = AppDatabase.forTesting(NativeDatabase.memory());
  });

  tearDown(() async {
    await db.close();
  });

  Future<void> seedBusinessData() async {
    await db
        .into(db.products)
        .insert(
          ProductsCompanion.insert(
            id: 'p1',
            name: 'Café',
            unitPrice: '1500',
            updatedAt: DateTime.now(),
          ),
        );
    await db
        .into(db.sales)
        .insert(
          SalesCompanion.insert(
            id: 's1',
            receiptNumber: 1,
            totalAmount: '1500',
            vatAmount: '0',
            paymentMethod: 'cash',
            createdAt: DateTime.now(),
          ),
        );
    await db
        .into(db.saleItems)
        .insert(
          SaleItemsCompanion.insert(
            id: 'si1',
            saleId: 's1',
            productId: 'p1',
            productName: 'Café',
            unitPrice: '1500',
            quantity: 1,
            lineTotal: '1500',
          ),
        );
    await db
        .into(db.syncQueue)
        .insert(
          SyncQueueCompanion.insert(
            entityType: 'product',
            entityId: 'p1',
            payload: '{}',
            createdAt: DateTime.now(),
          ),
        );
  }

  test('wipeBusinessData clears all business tables', () async {
    await seedBusinessData();
    await SyncMetadataStorage(db).setActiveStoreId('store-A');

    await LocalDataResetService(db).wipeBusinessData();

    expect(await db.select(db.products).get(), isEmpty);
    expect(await db.select(db.sales).get(), isEmpty);
    expect(await db.select(db.saleItems).get(), isEmpty);
    expect(await db.select(db.syncQueue).get(), isEmpty);
    expect(await db.select(db.syncMetadata).get(), isEmpty);
  });

  test('active store id round-trips and updates', () async {
    final meta = SyncMetadataStorage(db);
    expect(await meta.getActiveStoreId(), isNull);

    await meta.setActiveStoreId('store-A');
    expect(await meta.getActiveStoreId(), 'store-A');

    await meta.setActiveStoreId('store-B');
    expect(await meta.getActiveStoreId(), 'store-B');
  });
}
