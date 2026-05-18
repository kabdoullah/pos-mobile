import '../../../../core/network/api_models/store_dto.dart';
import '../../domain/entities/store.dart';

/// Maps StoreDto (API) → Store (domain).
extension StoreDtoToDomain on StoreDto {
  /// Converts API DTO to domain entity.
  Store toDomain() => Store(
    name: name,
    address: address,
    ncc: ncc,
    isSubjectToVat: vatSubject,
    receiptFooterText: receiptFooterText,
  );
}

/// Maps Store (domain) → StoreUpdateDto (API request).
extension StoreUpdateDtoMapper on Store {
  /// Converts domain entity to update request DTO.
  StoreUpdateDto toUpdateDto() => StoreUpdateDto(
    name: name,
    address: address,
    ncc: ncc,
    vatSubject: isSubjectToVat,
    receiptFooterText: receiptFooterText,
  );
}

/// Maps Store (domain) → StoreCreateDto (API request).
extension StoreCreateDtoMapper on Store {
  /// Converts domain entity to create request DTO.
  StoreCreateDto toCreateDto() => StoreCreateDto(
    name: name,
    address: address,
    ncc: ncc,
    vatSubject: isSubjectToVat,
    receiptFooterText: receiptFooterText,
  );
}
