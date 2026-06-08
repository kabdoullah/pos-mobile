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
  static final _log = Logger();

  static const int _lineWidth = 32;
  static const String _separator = '--------------------------------';
  static const String _doubleSeparator = '================================';

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
      generator.text('Date : ${dateFormatter.format(sale.createdAt)}'),
    );
    bytes.addAll(
      generator.text(
        sale.receiptNumber > 0
            ? 'Reçu N° ${sale.receiptNumber.toString().padLeft(6, '0')}'
            : 'Reçu : PROVISOIRE',
      ),
    );
    bytes.addAll(generator.text(_separator));

    // --- ITEMS ---
    if (items != null && items.isNotEmpty) {
      bytes.addAll(
        generator.text('${items.length} article${items.length > 1 ? 's' : ''}'),
      );
      for (final item in items) {
        bytes.addAll(_formatLineItem(generator, item));
      }
    } else {
      bytes.addAll(
        generator.text(
          'Ticket provisoire — articles non disponibles',
          styles: const PosStyles(align: PosAlign.center),
        ),
      );
    }
    bytes.addAll(generator.text(_separator));

    // --- TOTALS ---
    if (sale.vatAmount != Decimal.zero) {
      final htAmount = sale.totalAmount - sale.vatAmount;
      bytes.addAll(
        generator.text(_padLine('Sous-total HT', _formatFcfa(htAmount))),
      );
      bytes.addAll(
        generator.text(_padLine('TVA', _formatFcfa(sale.vatAmount))),
      );
      bytes.addAll(generator.text(_doubleSeparator));
      bytes.addAll(
        generator.text(
          _padLine('TOTAL TTC', _formatFcfa(sale.totalAmount)),
          styles: const PosStyles(bold: true),
        ),
      );
    } else {
      bytes.addAll(generator.text(_doubleSeparator));
      bytes.addAll(
        generator.text(
          _padLine('TOTAL', _formatFcfa(sale.totalAmount)),
          styles: const PosStyles(bold: true),
        ),
      );
    }
    bytes.addAll(generator.text(_separator));

    // --- PAYMENT ---
    bytes.addAll(generator.text('Mode : ${_paymentLabel(sale.paymentMethod)}'));
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
        'Merci de votre visite !',
        styles: const PosStyles(align: PosAlign.center),
      ),
    );
    bytes.addAll(generator.cut());

    _log.d('Receipt formatted: ${bytes.length} bytes');
    return bytes;
  }

  /// Two-line item: product name on line 1, qty × unit_price = total on line 2.
  static List<int> _formatLineItem(Generator gen, CartItem item) {
    final name = item.productName.length > _lineWidth
        ? '${item.productName.substring(0, _lineWidth - 3)}...'
        : item.productName;
    final detail = _padLine(
      '  ${item.quantity} x ${_formatFcfa(item.unitPrice)}',
      _formatFcfa(item.lineTotal),
    );
    return [...gen.text(name), ...gen.text(detail)];
  }

  /// Left-right aligned text padded to [_lineWidth] characters.
  static String _padLine(String left, String right) {
    final total = left.length + right.length;
    if (total >= _lineWidth) return '$left $right';
    return left + ' ' * (_lineWidth - total) + right;
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
      PaymentMethod.mtn => 'MTN Mobile Money',
      PaymentMethod.wave => 'Wave',
      PaymentMethod.mixed => 'Mixte',
    };
  }
}
