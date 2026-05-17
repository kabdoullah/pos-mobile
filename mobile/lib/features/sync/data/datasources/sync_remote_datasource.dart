import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../../../core/network/api_models/sale_dto.dart';
import '../../../../core/network/api_models/sync_changes_dto.dart';

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

  /// Pushes product changes to server (state-based sync).
  /// Endpoint: PUT /api/v1/sync/products
  @PUT('/api/v1/sync/products')
  Future<SyncResponseDto> pushProducts(@Body() ProductSyncBatchDto batch);

  /// Pushes a sale to server (event-based sync with idempotence).
  /// Endpoint: POST /api/v1/sync/sales
  @POST('/api/v1/sync/sales')
  Future<SyncResponseDto> pushSale(@Body() SaleCreateDto sale);
}
