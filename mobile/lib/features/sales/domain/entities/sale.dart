import 'package:decimal/decimal.dart';
import 'package:freezed_annotation/freezed_annotation.dart';

part 'sale.freezed.dart';

/// PaymentMethod enum — available payment methods.
enum PaymentMethod {
  /// Cash payment.
  cash,

  /// Orange Money (mobile money).
  orangeMoney,

  /// MTN mobile money.
  mtn,

  /// Wave mobile money.
  wave,

  /// Mixed payment (cash + mobile money).
  mixed,
}

/// Sale entity — immutable sale record.
@freezed
sealed class Sale with _$Sale {
  const factory Sale({
    required String id,
    required int receiptNumber,
    required Decimal totalAmount,
    required Decimal vatAmount,
    required PaymentMethod paymentMethod,
    required DateTime createdAt,
  }) = _Sale;
}
