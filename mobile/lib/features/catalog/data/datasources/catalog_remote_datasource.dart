import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../../../core/network/api_models/pagination.dart';
import '../../../../core/network/api_models/product_dto.dart';

part 'catalog_remote_datasource.g.dart';

/// Remote data source for catalog operations.
@RestApi()
abstract class CatalogRemoteDataSource {
  /// Creates a CatalogRemoteDataSource instance.
  factory CatalogRemoteDataSource(Dio dio, {String baseUrl}) =
      _CatalogRemoteDataSource;

  /// Lists products with pagination.
  /// Endpoint: GET /api/v1/products
  @GET('/api/v1/products')
  Future<CursorPageDto<ProductDto>> listProducts({
    @Query('cursor') String? cursor,
    @Query('limit') int? limit,
    @Query('search') String? search,
  });

  /// Gets a product by ID.
  /// Endpoint: GET /api/v1/products/{id}
  @GET('/api/v1/products/{id}')
  Future<ProductDto> getProduct(@Path('id') String id);

  /// Gets a product by barcode.
  /// Endpoint: GET /api/v1/products/by-barcode/{barcode}
  @GET('/api/v1/products/by-barcode/{barcode}')
  Future<ProductDto> getProductByBarcode(@Path('barcode') String barcode);

  /// Creates a new product.
  /// Endpoint: POST /api/v1/products
  @POST('/api/v1/products')
  Future<ProductDto> createProduct(@Body() ProductCreateDto request);

  /// Updates a product (PATCH).
  /// Endpoint: PATCH /api/v1/products/{id}
  @PATCH('/api/v1/products/{id}')
  Future<ProductDto> updateProduct(
    @Path('id') String id,
    @Body() ProductUpdateDto request,
  );

  /// Deletes a product (soft delete).
  /// Endpoint: DELETE /api/v1/products/{id}
  @DELETE('/api/v1/products/{id}')
  Future<void> deleteProduct(@Path('id') String id);
}
