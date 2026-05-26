import 'package:decimal/decimal.dart';
import 'package:esc_pos_utils_plus/esc_pos_utils_plus.dart';
import 'package:intl/intl.dart';
import 'package:logger/logger.dart';

import '../../auth/domain/entities/store.dart';
import '../../sales/domain/entities/cart_item.dart';
import '../../sales/domain/entities/sale.dart';

/// Formats receipt data into ESC/POS byte sequences for 58mm thermal paper.
///
/// Receipt width: 32 monospaced characters.
class ReceiptFormatter {
  /// Logger instance.
  static final _log = Logger();

  /// 32-character separator line.
  static const String _separator = '--------------------------------';

  /// Builds ESC/POS bytes for the given sale receipt.
  ///
  /// [items] may be null when printing from history (offline session data unavailable).
  /// Throws [Exception] if formatting fails.
  static Future<List<int>> format({
    required Store store,
    required Sale sale,
    List<CartItem>? items,
  }) async {
    final profile = await CapabilityProfile.load();
    final generator = Generator(PaperSize.mm58, profile);
    final bytes = <int>[];

    // --- HEADER ---
    bytes.addAll(
      generator.text(
        store.name,
        styles: const PosStyles(bold: true, align: PosAlign.center),
      ),
    );
    if (store.ncc != null && store.ncc!.isNotEmpty) {
      bytes.addAll(
        generator.text(
          'NCC: ${store.ncc}',
          styles: const PosStyles(align: PosAlign.center),
        ),
      );
    }
    if (store.address != null && store.address!.isNotEmpty) {
      bytes.addAll(
        generator.text(
          store.address!,
          styles: const PosStyles(align: PosAlign.center),
        ),
      );
    }
    bytes.addAll(generator.text(_separator));

    // --- DATE / RECEIPT INFO ---
    final dateFormatter = DateFormat('dd/MM/yyyy HH:mm', 'fr_FR');
    bytes.addAll(
      generator.text('Date: ${dateFormatter.format(sale.createdAt)}'),
    );

    // receipt_number is 0 until server assigns it after sync
    if (sale.receiptNumber > 0) {
      bytes.addAll(generator.text('Reçu N°: ${sale.receiptNumber}'));
    } else {
      bytes.addAll(generator.text('Reçu: PROVISOIRE'));
    }
    bytes.addAll(generator.text(_separator));

    // --- ITEMS ---
    if (items != null && items.isNotEmpty) {
      for (final item in items) {
        bytes.addAll(_formatLineItem(generator, item));
      }
    } else {
      bytes.addAll(
        generator.text(
          'Ticket provisoire - articles non disponibles',
          styles: const PosStyles(align: PosAlign.center),
        ),
      );
    }
    bytes.addAll(generator.text(_separator));

    // --- TOTAL ---
    bytes.addAll(
      generator.row([
        PosColumn(text: 'TOTAL', width: 6, styles: const PosStyles(bold: true)),
        PosColumn(
          text: _formatFcfa(sale.totalAmount),
          width: 6,
          styles: const PosStyles(bold: true, align: PosAlign.right),
        ),
      ]),
    );

    if (sale.vatAmount != Decimal.zero) {
      bytes.addAll(
        generator.row([
          PosColumn(text: 'TVA', width: 6),
          PosColumn(
            text: _formatFcfa(sale.vatAmount),
            width: 6,
            styles: const PosStyles(align: PosAlign.right),
          ),
        ]),
      );
    }

    bytes.addAll(generator.text('Mode: ${_paymentLabel(sale.paymentMethod)}'));
    bytes.addAll(generator.text(_separator));

    // --- FOOTER ---
    if (store.receiptFooterText != null &&
        store.receiptFooterText!.isNotEmpty) {
      bytes.addAll(
        generator.text(
          store.receiptFooterText!,
          styles: const PosStyles(align: PosAlign.center),
        ),
      );
    }
    bytes.addAll(
      generator.text(
        'Merci de votre visite',
        styles: const PosStyles(align: PosAlign.center),
      ),
    );
    bytes.addAll(generator.cut());

    _log.d('Receipt formatted: ${bytes.length} bytes');
    return bytes;
  }

  /// Formats a line item for the receipt.
  /// Product name is truncated to fit 32-char width.
  static List<int> _formatLineItem(Generator gen, CartItem item) {
    final lineTotal = item.lineTotal;
    // Truncate product name to 20 chars (leaves room for qty and amount)
    final name = item.productName.length > 20
        ? '${item.productName.substring(0, 17)}...'
        : item.productName;
    return gen.row([
      PosColumn(text: '$name x${item.quantity}', width: 9),
      PosColumn(
        text: _formatFcfa(lineTotal),
        width: 3,
        styles: const PosStyles(align: PosAlign.right),
      ),
    ]);
  }

  /// Formats a Decimal amount as localized FCFA string.
  static String _formatFcfa(Decimal amount) {
    return NumberFormat('#,##0', 'fr_FR').format(amount.toDouble());
  }

  /// Returns localized payment method label.
  static String _paymentLabel(PaymentMethod method) {
    return switch (method) {
      PaymentMethod.cash => 'Espèces',
      PaymentMethod.orangeMoney => 'Orange Money',
      PaymentMethod.mtn => 'MTN',
      PaymentMethod.wave => 'Wave',
      PaymentMethod.mixed => 'Mixte',
    };
  }
}
