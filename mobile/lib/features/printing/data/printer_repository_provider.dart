import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../domain/repositories/printer_repository.dart';
import 'printer_service.dart';

part 'printer_repository_provider.g.dart';

/// Provides a singleton [PrinterRepository] implementation.
///
/// Returns the abstract interface; consumers should not depend on
/// the concrete [PrinterService] implementation.
@riverpod
PrinterRepository printerRepository(Ref ref) => const PrinterService();
