import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';

part 'app_database.g.dart';

/// Table des produits du catalogue local.
class Products extends Table {
  /// UUID v4 généré côté client.
  TextColumn get id => text()();

  /// Nom du produit.
  TextColumn get name => text().withLength(min: 1, max: 255)();

  /// Code-barres optionnel.
  TextColumn get barcode => text().nullable()();

  /// Prix unitaire en FCFA, stocké en string pour préserver la précision.
  TextColumn get unitPrice => text()();

  /// Stock actuel (null = stock non géré).
  IntColumn get currentStock => integer().nullable()();

  /// Marqué pour synchronisation.
  BoolColumn get dirty => boolean().withDefault(const Constant(false))();

  /// Dernière modification locale.
  DateTimeColumn get updatedAt => dateTime()();

  /// Soft delete.
  DateTimeColumn get deletedAt => dateTime().nullable()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Table des ventes locales.
class Sales extends Table {
  /// UUID v4 généré côté client (idempotence sync).
  TextColumn get id => text()();

  /// Numéro de reçu séquentiel.
  IntColumn get receiptNumber => integer()();

  /// Total TTC en FCFA.
  TextColumn get totalAmount => text()();

  /// Montant TVA.
  TextColumn get vatAmount => text()();

  /// Mode de paiement.
  TextColumn get paymentMethod => text()();

  /// Date de création.
  DateTimeColumn get createdAt => dateTime()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Lignes de vente.
class SaleItems extends Table {
  /// UUID v4 généré côté client.
  TextColumn get id => text()();

  /// Référence à la vente (FK).
  TextColumn get saleId => text()();

  /// UUID du produit.
  TextColumn get productId => text()();

  /// Nom du produit au moment de la vente.
  TextColumn get productName => text()();

  /// Prix unitaire en FCFA, stocké en string.
  TextColumn get unitPrice => text()();

  /// Quantité.
  IntColumn get quantity => integer()();

  /// Total ligne en FCFA, stocké en string.
  TextColumn get lineTotal => text()();

  @override
  Set<Column> get primaryKey => {id};
}

/// Métadonnées de synchronisation — stocke les timestamps du dernier pull.
class SyncMetadata extends Table {
  /// Clé unique (ex: 'last_pull').
  TextColumn get key => text()();

  /// Valeur du timestamp (ISO 8601).
  TextColumn get value => text()();

  /// Dernière mise à jour.
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {key};
}

/// File d'attente locale pour la synchronisation.
class SyncQueue extends Table {
  /// Auto-incrémenté.
  IntColumn get id => integer().autoIncrement()();

  /// Type d'entité (sale, product, etc.).
  TextColumn get entityType => text()();

  /// UUID de l'entité concernée.
  TextColumn get entityId => text()();

  /// Payload JSON sérialisé.
  TextColumn get payload => text()();

  /// pending, syncing, synced, failed.
  TextColumn get status => text().withDefault(const Constant('pending'))();

  /// Nombre de tentatives.
  IntColumn get retryCount => integer().withDefault(const Constant(0))();

  /// Dernière erreur rencontrée.
  TextColumn get lastError => text().nullable()();

  /// Horodatage de création.
  DateTimeColumn get createdAt => dateTime()();

  /// Horodatage de la dernière tentative de sync.
  DateTimeColumn get lastAttemptAt => dateTime().nullable()();
}

/// Base de données drift de l'application.
@DriftDatabase(tables: [Products, Sales, SaleItems, SyncQueue, SyncMetadata])
class AppDatabase extends _$AppDatabase {
  /// Constructor.
  AppDatabase() : super(_openConnection());

  /// Version courante du schéma drift.
  @override
  int get schemaVersion => 4;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (m) => m.createAll(),
    onUpgrade: (m, from, to) async {
      if (from < 3) {
        // Pre-production schemas: drop all and recreate.
        await customStatement('DROP TABLE IF EXISTS sale_items');
        await customStatement('DROP TABLE IF EXISTS sales');
        await customStatement('DROP TABLE IF EXISTS products');
        await customStatement('DROP TABLE IF EXISTS sync_queue');
        await customStatement('DROP TABLE IF EXISTS sync_metadata');
        await m.createAll();
      } else {
        // v3 → v4: remove (saleId, productId) unique constraint from sale_items.
        // SQLite cannot drop constraints in-place — rebuild via temp table.
        await customStatement(
          'CREATE TABLE sale_items_new ('
          '  id TEXT NOT NULL PRIMARY KEY,'
          '  sale_id TEXT NOT NULL,'
          '  product_id TEXT NOT NULL,'
          '  product_name TEXT NOT NULL,'
          '  unit_price TEXT NOT NULL,'
          '  quantity INTEGER NOT NULL,'
          '  line_total TEXT NOT NULL'
          ')',
        );
        await customStatement(
          'INSERT INTO sale_items_new SELECT id, sale_id, product_id,'
          ' product_name, unit_price, quantity, line_total FROM sale_items',
        );
        await customStatement('DROP TABLE sale_items');
        await customStatement(
          'ALTER TABLE sale_items_new RENAME TO sale_items',
        );
      }
    },
  );

  static QueryExecutor _openConnection() {
    return driftDatabase(name: 'pos_mobile');
  }
}
