import 'package:logger/logger.dart';
import 'package:print_bluetooth_thermal/print_bluetooth_thermal.dart';

import '../../auth/domain/entities/store.dart';
import '../../sales/domain/entities/cart_item.dart';
import '../../sales/domain/entities/sale.dart';
import '../domain/repositories/printer_repository.dart';
import 'receipt_formatter.dart';

/// Orchestrates BT discovery, connection, and data transmission.
///
/// Uses [print_bluetooth_thermal] for all BT operations.
/// Does NOT maintain persistent connection state — that is managed by [PrinterProvider].
class PrinterService implements PrinterRepository {
  /// Creates a [PrinterService].
  const PrinterService();

  static final _log = Logger();

  /// Lists all paired BT devices available on the system.
  @override
  Future<List<BluetoothInfo>> getPairedDevices() async {
    return PrintBluetoothThermal.pairedBluetooths;
  }

  /// Connects to the device at [mac].
  ///
  /// Returns true on success. Throws [PrintException] on failure.
  /// Note: [PrintBluetoothThermal.disconnect] is a getter, not a method.
  @override
  Future<bool> connect(String mac) async {
    _log.i('Connecting to BT device: $mac');
    final result = await PrintBluetoothThermal.connect(macPrinterAddress: mac);
    if (!result) {
      throw PrintException(
        reason: PrintFailureReason.connectionFailed,
        details: 'Could not connect to $mac',
      );
    }
    return result;
  }

  /// Disconnects from the current BT device.
  @override
  Future<void> disconnect() async {
    // Note: disconnect is a getter, not a method in print_bluetooth_thermal v1.2.x
    await PrintBluetoothThermal.disconnect;
  }

  /// Returns true if currently connected to a BT device.
  @override
  Future<bool> get isConnected => PrintBluetoothThermal.connectionStatus;

  /// Prints a receipt for [sale].
  ///
  /// Formats bytes via [ReceiptFormatter] and sends to the connected printer.
  /// Throws [PrintException] if not connected or send fails.
  @override
  Future<void> printReceipt({
    required Store store,
    required Sale sale,
    List<CartItem>? items,
  }) async {
    final connected = await isConnected;
    if (!connected) {
      throw const PrintException(
        reason: PrintFailureReason.connectionFailed,
        details: 'Printer not connected',
      );
    }
    final bytes = await ReceiptFormatter.format(
      store: store,
      sale: sale,
      items: items,
    );
    final result = await PrintBluetoothThermal.writeBytes(bytes);
    if (!result) {
      throw const PrintException(
        reason: PrintFailureReason.sendFailed,
        details: 'Failed to send data to printer',
      );
    }
    _log.i('Receipt printed successfully');
  }
}
