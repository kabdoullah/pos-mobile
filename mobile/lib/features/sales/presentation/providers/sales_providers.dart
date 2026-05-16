import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../domain/entities/sale.dart';
import '../../domain/repositories/sales_repository.dart';
import '../../../catalog/domain/entities/product.dart';
import '../../../catalog/presentation/providers/catalog_providers.dart';
import 'cart_provider.dart';

part 'sales_providers.g.dart';

// TODO: Implement SalesRepository with drift/retrofit data layer
class _SalesRepositoryImpl implements SalesRepository {
  @override
  Future<Sale> createSale({
    required String totalAmount,
    required String vatAmount,
    required PaymentMethod paymentMethod,
  }) async {
    // TODO: Create sale in drift DB, sync to API
    throw UnimplementedError();
  }

  @override
  Future<List<Sale>> getSales({String? cursor, int limit = 50}) async {
    // TODO: Query drift DB
    return [];
  }

  @override
  Future<Sale?> getSale(String id) async {
    // TODO: Query drift DB
    return null;
  }
}

/// Provides the sales repository instance.
@riverpod
SalesRepository salesRepository(Ref ref) {
  return _SalesRepositoryImpl();
}

/// Submit current cart as a sale.
@riverpod
Future<Sale> submitSale(
  Ref ref, {
  required String totalAmount,
  required String vatAmount,
  required PaymentMethod paymentMethod,
}) async {
  final repo = ref.watch(salesRepositoryProvider);

  // TODO: Add cart items as line items to sync queue
  final cartState = ref.watch(cartProvider);

  final sale = await repo.createSale(
    totalAmount: totalAmount,
    vatAmount: vatAmount,
    paymentMethod: paymentMethod,
  );

  // Clear cart after successful submission
  ref.read(cartProvider.notifier).clear();

  return sale;
}

/// Loads sales for a specific date from local Drift DB.
///
/// TODO: Query Drift: SELECT * FROM Sales WHERE date(createdAt) = date(date) ORDER BY createdAt DESC
/// TODO: Implement after SalesRepository Drift data layer lands
@riverpod
Future<List<Sale>> salesHistory(Ref ref, {required DateTime date}) async {
  return [];
}
