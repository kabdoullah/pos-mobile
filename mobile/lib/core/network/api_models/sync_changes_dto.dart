import 'package:freezed_annotation/freezed_annotation.dart';

import 'product_dto.dart';
import 'sale_dto.dart';

part 'sync_changes_dto.freezed.dart';
part 'sync_changes_dto.g.dart';

/// Response from GET /api/v1/sync/changes.
@freezed
sealed class SyncChangesDto with _$SyncChangesDto {
  /// Creates a [SyncChangesDto].
  const factory SyncChangesDto({
    required List<ProductDto> products,
    required List<SaleDto> sales,
    @JsonKey(name: 'next_cursor') String? nextCursor,
    @JsonKey(name: 'has_more') required bool hasMore,
    @JsonKey(name: 'server_time') required String serverTime,
  }) = _SyncChangesDto;

  factory SyncChangesDto.fromJson(Map<String, dynamic> json) =>
      _$SyncChangesDtoFromJson(json);
}

/// Request body for PUT /api/v1/sync/products (state-based sync).
@freezed
sealed class ProductSyncBatchDto with _$ProductSyncBatchDto {
  /// Creates a [ProductSyncBatchDto].
  const factory ProductSyncBatchDto({required List<ProductSyncItemDto> items}) =
      _ProductSyncBatchDto;

  factory ProductSyncBatchDto.fromJson(Map<String, dynamic> json) =>
      _$ProductSyncBatchDtoFromJson(json);
}

/// Single product for sync batch.
@freezed
sealed class ProductSyncItemDto with _$ProductSyncItemDto {
  /// Creates a [ProductSyncItemDto].
  const factory ProductSyncItemDto({
    required String id,
    required String name,
    String? barcode,
    @JsonKey(name: 'unit_price') required String unitPrice,
    @JsonKey(name: 'current_stock') int? currentStock,
    @JsonKey(name: 'client_updated_at') required String clientUpdatedAt,
    @Default(false) bool deleted,
  }) = _ProductSyncItemDto;

  factory ProductSyncItemDto.fromJson(Map<String, dynamic> json) =>
      _$ProductSyncItemDtoFromJson(json);
}

/// Response from sync endpoints.
@freezed
sealed class SyncResponseDto with _$SyncResponseDto {
  /// Creates a [SyncResponseDto].
  const factory SyncResponseDto({
    required String message,
    @JsonKey(name: 'synced_count') required int syncedCount,
  }) = _SyncResponseDto;

  factory SyncResponseDto.fromJson(Map<String, dynamic> json) =>
      _$SyncResponseDtoFromJson(json);
}
