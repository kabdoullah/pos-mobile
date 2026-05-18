import 'package:drift/drift.dart' as drift;

import '../../../../core/network/api_models/sale_dto.dart';
import '../../../../database/app_database.dart' as drift_db;
import '../../domain/entities/sale.dart' as domain;

/// Maps PaymentMethodDto (API) → domain.PaymentMethod.
domain.PaymentMethod _paymentMethodFromString(String method) {
  return switch (method) {
    'cash' => domain.PaymentMethod.cash,
    'mobile_money_orange' => domain.PaymentMethod.orangeMoney,
    'mobile_money_mtn' => domain.PaymentMethod.mtn,
    'mobile_money_wave' => domain.PaymentMethod.wave,
    'mixed' => domain.PaymentMethod.mixed,
    _ => domain.PaymentMethod.cash,
  };
}

/// Maps domain.PaymentMethod → string (API).
String _paymentMethodToString(domain.PaymentMethod method) {
  return switch (method) {
    domain.PaymentMethod.cash => 'cash',
    domain.PaymentMethod.orangeMoney => 'mobile_money_orange',
    domain.PaymentMethod.mtn => 'mobile_money_mtn',
    domain.PaymentMethod.wave => 'mobile_money_wave',
    domain.PaymentMethod.mixed => 'mixed',
  };
}

/// Maps SaleDto (API) → domain.Sale.
extension SaleDtoToDomain on SaleDto {
  /// Converts API DTO to domain entity.
  domain.Sale toDomain() => domain.Sale(
    id: id,
    receiptNumber: receiptNumber ?? 0,
    totalAmount: totalAmount,
    vatAmount: vatAmount,
    paymentMethod: _paymentMethodFromString(paymentMethod),
    createdAt: DateTime.parse(createdAt),
  );
}

/// Maps domain.Sale → drift SalesCompanion.
extension DomainSaleToDrift on domain.Sale {
  /// Converts domain entity to drift companion.
  drift_db.SalesCompanion toDriftCompanion() => drift_db.SalesCompanion(
    id: drift.Value(id),
    receiptNumber: drift.Value(receiptNumber),
    totalAmount: drift.Value(totalAmount),
    vatAmount: drift.Value(vatAmount),
    paymentMethod: drift.Value(_paymentMethodToString(paymentMethod)),
    createdAt: drift.Value(createdAt),
  );
}

/// Maps drift Sale row → domain.Sale.
extension DriftSaleToDomain on drift_db.Sale {
  /// Converts drift row to domain entity.
  domain.Sale toDomain() => domain.Sale(
    id: id,
    receiptNumber: receiptNumber,
    totalAmount: totalAmount,
    vatAmount: vatAmount,
    paymentMethod: _paymentMethodFromString(paymentMethod),
    createdAt: createdAt,
  );
}

/// Maps domain.Sale → SaleCreateDto (API request).
extension DomainSaleCreateDtoMapper on domain.Sale {
  /// Converts domain entity to create request DTO.
  SaleCreateDto toCreateDto({
    required List<SaleItemCreateDto> items,
    String? cashAmount,
    String? mobileMoneyAmount,
  }) => SaleCreateDto(
    id: id,
    items: items,
    totalAmount: totalAmount,
    vatAmount: vatAmount,
    paymentMethod: switch (paymentMethod) {
      domain.PaymentMethod.cash => PaymentMethodDto.cash,
      domain.PaymentMethod.orangeMoney => PaymentMethodDto.mobileMoneyOrange,
      domain.PaymentMethod.mtn => PaymentMethodDto.mobileMoneyMtn,
      domain.PaymentMethod.wave => PaymentMethodDto.mobileMoneyWave,
      domain.PaymentMethod.mixed => PaymentMethodDto.mixed,
    },
    cashAmount: cashAmount,
    mobileMoneyAmount: mobileMoneyAmount,
    createdAt: createdAt.toIso8601String(),
  );
}
