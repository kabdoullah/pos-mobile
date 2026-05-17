import 'package:freezed_annotation/freezed_annotation.dart';

part 'store_dto.freezed.dart';
part 'store_dto.g.dart';

/// Store data transfer object from API.
@freezed
sealed class StoreDto with _$StoreDto {
  /// Creates a [StoreDto].
  const factory StoreDto({
    required String id,
    @JsonKey(name: 'owner_id') required String ownerId,
    required String name,
    String? address,
    String? ncc,
    @JsonKey(name: 'vat_subject') required bool vatSubject,
    @JsonKey(name: 'receipt_footer_text') String? receiptFooterText,
    @JsonKey(name: 'next_receipt_number') required int nextReceiptNumber,
    @JsonKey(name: 'created_at') required String createdAt,
    @JsonKey(name: 'updated_at') required String updatedAt,
  }) = _StoreDto;

  factory StoreDto.fromJson(Map<String, dynamic> json) =>
      _$StoreDtoFromJson(json);
}

/// Request to create a store.
@freezed
sealed class StoreCreateDto with _$StoreCreateDto {
  /// Creates a [StoreCreateDto].
  const factory StoreCreateDto({
    required String name,
    String? address,
    String? ncc,
    @JsonKey(name: 'vat_subject') bool? vatSubject,
    @JsonKey(name: 'receipt_footer_text') String? receiptFooterText,
  }) = _StoreCreateDto;

  factory StoreCreateDto.fromJson(Map<String, dynamic> json) =>
      _$StoreCreateDtoFromJson(json);
}

/// Request to update a store (PATCH).
@freezed
sealed class StoreUpdateDto with _$StoreUpdateDto {
  /// Creates a [StoreUpdateDto].
  const factory StoreUpdateDto({
    String? name,
    String? address,
    String? ncc,
    @JsonKey(name: 'vat_subject') bool? vatSubject,
    @JsonKey(name: 'receipt_footer_text') String? receiptFooterText,
  }) = _StoreUpdateDto;

  factory StoreUpdateDto.fromJson(Map<String, dynamic> json) =>
      _$StoreUpdateDtoFromJson(json);
}
