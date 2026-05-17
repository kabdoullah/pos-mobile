import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../../../core/network/api_models/pagination.dart';
import '../../../../core/network/api_models/sale_dto.dart';

part 'sales_remote_datasource.g.dart';

/// Remote data source for sales operations.
@RestApi()
abstract class SalesRemoteDataSource {
  /// Creates a SalesRemoteDataSource instance.
  factory SalesRemoteDataSource(Dio dio, {String baseUrl}) =
      _SalesRemoteDataSource;

  /// Lists sales with pagination.
  /// Endpoint: GET /api/v1/sales
  @GET('/api/v1/sales')
  Future<CursorPageDto<SaleDto>> listSales({
    @Query('cursor') String? cursor,
    @Query('limit') int? limit,
    @Query('date_from') String? dateFrom,
    @Query('date_to') String? dateTo,
  });

  /// Gets a sale by ID.
  /// Endpoint: GET /api/v1/sales/{id}
  @GET('/api/v1/sales/{id}')
  Future<SaleDto> getSale(@Path('id') String id);

  /// Gets today's sales summary.
  /// Endpoint: GET /api/v1/sales/today/summary
  @GET('/api/v1/sales/today/summary')
  Future<DailySalesSummaryDto> getTodaySalesSummary();

  /// Creates a sale.
  /// Endpoint: POST /api/v1/sales
  @POST('/api/v1/sales')
  Future<SaleDto> createSale(@Body() SaleCreateDto request);
}
