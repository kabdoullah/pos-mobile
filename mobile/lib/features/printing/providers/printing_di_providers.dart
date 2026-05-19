import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../data/printer_service.dart';
import '../domain/repositories/printer_repository.dart';

part 'printing_di_providers.g.dart';

/// Provides a singleton [PrinterRepository] implementation.
///
/// Returns the abstract interface; consumers should not depend on
/// the concrete [PrinterService] implementation.
@riverpod
PrinterRepository printerRepository(Ref ref) => const PrinterService();
