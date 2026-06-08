import 'dart:async';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:logger/logger.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../domain/repositories/printer_repository.dart';
import '../../providers/printing_di_providers.dart';
import '../../../auth/providers/store_provider.dart';
import '../../../sales/domain/entities/cart_item.dart';
import '../../../sales/domain/entities/sale.dart';

part 'printer_provider.g.dart';

/// Storage keys for printer preferences in flutter_secure_storage.
abstract class _PrinterKeys {
  /// Saved printer MAC address key.
  static const String mac = 'printer_mac';

  /// Saved printer device name key.
  static const String name = 'printer_name';
}

/// Sealed state for the Bluetooth printer.
sealed class PrinterState {
  /// Creates a [PrinterState].
  const PrinterState();
}

/// No printer connected; may have a saved MAC from a previous session.
class PrinterDisconnected extends PrinterState {
  /// Creates a [PrinterDisconnected] state.
  const PrinterDisconnected({this.savedMac, this.savedName});

  /// Saved MAC from secure storage, if any.
  final String? savedMac;

  /// Saved device name from secure storage, if any.
  final String? savedName;
}

/// Currently attempting to connect to a printer.
class PrinterConnecting extends PrinterState {
  /// Creates a [PrinterConnecting] state.
  const PrinterConnecting();
}

/// Successfully connected to a BT printer.
class PrinterConnected extends PrinterState {
  /// Creates a [PrinterConnected] state.
  const PrinterConnected({required this.mac, required this.name});

  /// MAC address of the connected printer.
  final String mac;

  /// Display name of the connected printer.
  final String name;
}

/// An error occurred during connection or printing.
class PrinterError extends PrinterState {
  /// Creates a [PrinterError] state.
  const PrinterError({required this.message, this.savedMac});

  /// Human-readable error message.
  final String message;

  /// Saved MAC, if available (for reconnect UI).
  final String? savedMac;
}

/// Manages Bluetooth printer connection lifecycle and printing.
@riverpod
class Printer extends _$Printer {
  static const _storage = FlutterSecureStorage();
  static final _log = Logger();

  @override
  PrinterState build() {
    unawaited(_loadSavedPrinter());
    return const PrinterDisconnected();
  }

  /// Loads saved printer info from secure storage asynchronously.
  /// Updates state once loaded.
  Future<void> _loadSavedPrinter() async {
    final mac = await _storage.read(key: _PrinterKeys.mac);
    final name = await _storage.read(key: _PrinterKeys.name);
    if (mac != null && state is PrinterDisconnected) {
      // Only update if still disconnected (not in an active operation)
      state = PrinterDisconnected(savedMac: mac, savedName: name);
    }
  }

  /// Connects to the BT device at [mac] with display [name].
  ///
  /// Updates state to [PrinterConnecting], then [PrinterConnected] or [PrinterError].
  Future<void> connect(String mac, String name) async {
    state = const PrinterConnecting();
    try {
      final service = ref.read(printerRepositoryProvider);
      await service.connect(mac);
      await _storage.write(key: _PrinterKeys.mac, value: mac);
      await _storage.write(key: _PrinterKeys.name, value: name);
      state = PrinterConnected(mac: mac, name: name);
      _log.i('Printer connected: $name ($mac)');
    } on PrintException catch (e) {
      state = PrinterError(message: e.details, savedMac: mac);
    } catch (e) {
      state = PrinterError(message: e.toString(), savedMac: mac);
    }
  }

  /// Disconnects the current BT printer.
  Future<void> disconnect() async {
    final service = ref.read(printerRepositoryProvider);
    final current = state;
    await service.disconnect();
    if (current is PrinterConnected) {
      state = PrinterDisconnected(
        savedMac: current.mac,
        savedName: current.name,
      );
    } else {
      state = const PrinterDisconnected();
    }
  }

  /// Prints a receipt. Reconnects if necessary using saved MAC.
  ///
  /// Throws [PrintException] if printer not configured or send fails.
  Future<void> print({required Sale sale, List<CartItem>? items}) async {
    final storeAsync = ref.read(storeConfigProvider);
    final store = storeAsync.whenOrNull(data: (s) => s);
    if (store == null) {
      throw const PrintException(
        reason: PrintFailureReason.noPrinterConfigured,
        details: 'Store not configured',
      );
    }

    final service = ref.read(printerRepositoryProvider);

    // Auto-reconnect if we have a saved MAC and not connected
    if (state is! PrinterConnected) {
      final savedMac = switch (state) {
        PrinterDisconnected(:final savedMac) => savedMac,
        PrinterError(:final savedMac) => savedMac,
        _ => null,
      };

      if (savedMac == null) {
        throw const PrintException(
          reason: PrintFailureReason.noPrinterConfigured,
          details: 'No printer configured',
        );
      }

      final savedName = await _storage.read(key: _PrinterKeys.name) ?? savedMac;
      await connect(savedMac, savedName);
    }

    await service.printReceipt(store: store, sale: sale, items: items);
    // Libère le lien BT immédiatement après impression.
    await service.disconnect();
    state = PrinterDisconnected(
      savedMac: switch (state) {
        PrinterConnected(:final mac) => mac,
        _ => null,
      },
      savedName: switch (state) {
        PrinterConnected(:final name) => name,
        _ => null,
      },
    );
  }
}
