import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../../../core/network/api_models/sale_dto.dart';
import '../../../../core/network/api_models/sync_changes_dto.dart';
import '../../../../core/network/api_models/sync_responses_dto.dart';

part 'sync_remote_datasource.g.dart';

/// Remote data source for sync operations.
@RestApi()
abstract class SyncRemoteDataSource {
  /// Creates a SyncRemoteDataSource instance.
  factory SyncRemoteDataSource(Dio dio, {String baseUrl}) =
      _SyncRemoteDataSource;

  /// Fetches changes (products and sales) since a given timestamp.
  /// Endpoint: GET /api/v1/sync/changes
  @GET('/api/v1/sync/changes')
  Future<SyncChangesDto> getChanges({
    @Query('since') String? since,
    @Query('limit') int? limit,
    @Query('cursor') String? cursor,
  });

  /// Pushes a batch of sales to server (event-based sync with idempotence).
  /// Endpoint: POST /api/v1/sync/sales
  @POST('/api/v1/sync/sales')
  Future<SalesSyncBatchResponseDto> pushSales(
    @Body() SalesSyncBatchRequestDto batch,
  );

  /// Pushes a single product change to server (state-based sync).
  /// Endpoint: PUT /api/v1/sync/products
  @PUT('/api/v1/sync/products')
  Future<ProductSyncResponseDto> pushProduct(
    @Body() ProductSyncItemDto product,
  );
}
