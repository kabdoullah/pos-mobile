import 'package:print_bluetooth_thermal/print_bluetooth_thermal.dart';

import '../../../auth/domain/entities/store.dart';
import '../../../sales/domain/entities/cart_item.dart';
import '../../../sales/domain/entities/sale.dart';

/// Reasons a print operation can fail.
enum PrintFailureReason {
  /// No printer MAC address has been saved.
  noPrinterConfigured,

  /// BT connection attempt failed or timed out.
  connectionFailed,

  /// Data could not be sent to the printer.
  sendFailed,
}

/// Thrown when printing fails.
class PrintException implements Exception {
  /// Creates a [PrintException].
  const PrintException({required this.reason, required this.details});

  /// The underlying failure cause.
  final PrintFailureReason reason;

  /// Human-readable error detail string.
  final String details;

  @override
  String toString() => 'PrintException(${reason.name}): $details';
}

/// Repository for Bluetooth printer operations.
///
/// Abstracts hardware interactions and connection management.
abstract interface class PrinterRepository {
  /// Lists all paired BT devices available on the system.
  Future<List<BluetoothInfo>> getPairedDevices();

  /// Connects to the device at [mac].
  ///
  /// Returns true on success. Throws [PrintException] on failure.
  Future<bool> connect(String mac);

  /// Disconnects from the current BT device.
  Future<void> disconnect();

  /// Returns true if currently connected to a BT device.
  Future<bool> get isConnected;

  /// Prints a receipt for [sale].
  ///
  /// Throws [PrintException] if not connected or send fails.
  Future<void> printReceipt({
    required Store store,
    required Sale sale,
    List<CartItem>? items,
  });
}
