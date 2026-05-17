import 'package:freezed_annotation/freezed_annotation.dart';

import 'product_dto.dart';
import 'sale_dto.dart';

part 'sync_responses_dto.freezed.dart';
part 'sync_responses_dto.g.dart';

/// Request to push a batch of sales.
@freezed
sealed class SalesSyncBatchRequestDto with _$SalesSyncBatchRequestDto {
  /// Creates a [SalesSyncBatchRequestDto].
  const factory SalesSyncBatchRequestDto({required List<SaleCreateDto> sales}) =
      _SalesSyncBatchRequestDto;

  factory SalesSyncBatchRequestDto.fromJson(Map<String, dynamic> json) =>
      _$SalesSyncBatchRequestDtoFromJson(json);
}

/// Single sale result from POST /api/v1/sync/sales batch.
@freezed
sealed class SaleSyncResultDto with _$SaleSyncResultDto {
  /// Creates a [SaleSyncResultDto].
  const factory SaleSyncResultDto({
    required String id,
    required String status, // 'created', 'already_exists', 'failed'
    @JsonKey(name: 'receipt_number') int? receiptNumber,
    String? error,
  }) = _SaleSyncResultDto;

  factory SaleSyncResultDto.fromJson(Map<String, dynamic> json) =>
      _$SaleSyncResultDtoFromJson(json);
}

/// Response from POST /api/v1/sync/sales.
@freezed
sealed class SalesSyncBatchResponseDto with _$SalesSyncBatchResponseDto {
  /// Creates a [SalesSyncBatchResponseDto].
  const factory SalesSyncBatchResponseDto({
    required int processed,
    required List<SaleSyncResultDto> results,
  }) = _SalesSyncBatchResponseDto;

  factory SalesSyncBatchResponseDto.fromJson(Map<String, dynamic> json) =>
      _$SalesSyncBatchResponseDtoFromJson(json);
}

/// Response from PUT /api/v1/sync/products.
@freezed
sealed class ProductSyncResponseDto with _$ProductSyncResponseDto {
  /// Creates a [ProductSyncResponseDto].
  const factory ProductSyncResponseDto({
    required String
    status, // 'created', 'updated', 'no_change', 'deleted', 'conflict'
    @JsonKey(name: 'server_state') ProductDto? serverState,
  }) = _ProductSyncResponseDto;

  factory ProductSyncResponseDto.fromJson(Map<String, dynamic> json) =>
      _$ProductSyncResponseDtoFromJson(json);
}
