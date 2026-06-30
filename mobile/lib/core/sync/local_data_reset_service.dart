import '../../database/app_database.dart';

/// Efface toutes les données métier locales (drift).
/// Appelé au changement de commerçant pour éviter la fuite cross-tenant.
class LocalDataResetService {
  /// Crée le service avec l'instance drift.
  const LocalDataResetService(this._db);

  final AppDatabase _db;

  /// Supprime produits, ventes, lignes de vente, file de sync et metadata.
  /// Transaction unique : tout ou rien.
  Future<void> wipeBusinessData() async {
    await _db.transaction(() async {
      await _db.delete(_db.saleItems).go();
      await _db.delete(_db.sales).go();
      await _db.delete(_db.products).go();
      await _db.delete(_db.syncQueue).go();
      await _db.delete(_db.syncMetadata).go();
    });
  }
}
