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
@DriftDatabase(tables: [Products, Sales, SyncQueue])
class AppDatabase extends _$AppDatabase {
  /// Constructor.
  AppDatabase() : super(_openConnection());

  /// Version courante du schéma drift.
  @override
  int get schemaVersion => 1;

  static QueryExecutor _openConnection() {
    return driftDatabase(name: 'pos_mobile');
  }
}
