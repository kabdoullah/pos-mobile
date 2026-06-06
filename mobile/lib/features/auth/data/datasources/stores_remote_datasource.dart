import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../../../core/network/api_models/store_dto.dart';

part 'stores_remote_datasource.g.dart';

/// Remote data source for store operations.
@RestApi()
abstract class StoresRemoteDataSource {
  /// Creates a StoresRemoteDataSource instance.
  factory StoresRemoteDataSource(Dio dio, {String baseUrl}) =
      _StoresRemoteDataSource;

  /// Gets the current user's store.
  /// Endpoint: GET /api/v1/stores/me
  @GET('/api/v1/stores/me')
  Future<StoreDto> getCurrentStore();

  /// Updates the current user's store.
  /// Endpoint: PATCH /api/v1/stores/me
  @PATCH('/api/v1/stores/me')
  Future<StoreDto> updateStore(@Body() StoreUpdateDto request);

  /// Creates a new store.
  /// Endpoint: POST /api/v1/stores
  @POST('/api/v1/stores')
  Future<StoreDto> createStore(@Body() StoreCreateDto request);
}
