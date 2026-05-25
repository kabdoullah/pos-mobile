import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/illustrations.dart';
import '../../../../shared/widgets/index.dart';
import '../../../sales/presentation/providers/cart_provider.dart';
import '../providers/catalog_providers.dart';

class CatalogPage extends ConsumerStatefulWidget {
  const CatalogPage({super.key});

  @override
  ConsumerState<CatalogPage> createState() => _CatalogPageState();
}

class _CatalogPageState extends ConsumerState<CatalogPage> {
  late TextEditingController _searchController;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    ref.read(searchQueryProvider.notifier).updateQuery(query);
  }

  Future<void> _onRefresh() async {
    await ref.read(catalogListProvider.notifier).refresh();
  }

  void _openProductForm({String? productId}) {
    if (productId == null) {
      unawaited(context.push(Routes.productNew));
    } else {
      unawaited(
        context.push(Routes.productEdit.replaceFirst(':id', productId)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.watch(debouncedSearchProvider);
    final catalogState = ref.watch(catalogListProvider);
    final cartState = ref.watch(cartProvider);

    return AppScaffold(
      title: 'Catalogue',
      floatingActionButton: FloatingActionButton(
        backgroundColor: AppColors.primary,
        onPressed: _openProductForm,
        child: const Icon(Icons.add, color: AppColors.textOnPrimary),
      ),
      body: Stack(
        children: [
          Column(
            children: [
              // Search bar
              Padding(
            padding: EdgeInsets.all(
              responsiveValue(
                context,
                small: AppSpacing.md,
                medium: AppSpacing.lg,
              ),
            ),
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                boxShadow: [
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.08),
                    blurRadius: 4,
                    offset: const Offset(0, 1),
                  ),
                ],
              ),
              child: AppTextField(
                label: 'Rechercher',
                hint: 'Nom du produit...',
                controller: _searchController,
                prefixIcon: Icons.search,
                onChanged: _onSearchChanged,
              ),
            ),
          ),
          // Product list
          Expanded(
            child: catalogState.when(
              loading: () => const AppLoadingScreen(),
              error: (error, stack) => EmptyStateIllustrated(
                illustration: Illustrations.errorState,
                title: 'Erreur',
                message: 'Impossible de charger le catalogue',
                actionLabel: 'Réessayer',
                onAction: _onRefresh,
              ),
              data: (products) {
                if (products.isEmpty) {
                  return EmptyStateIllustrated(
                    illustration: Illustrations.emptyCatalog,
                    title: 'Aucun produit',
                    message: 'Commencez par ajouter votre premier produit',
                    actionLabel: 'Ajouter un produit',
                    onAction: _openProductForm,
                  );
                }

                return RefreshIndicator(
                  onRefresh: _onRefresh,
                  color: AppColors.primary,
                  backgroundColor: AppColors.primaryContainer,
                  strokeWidth: 3,
                  child: ListView.builder(
                    padding: EdgeInsets.symmetric(
                      horizontal: responsiveValue(
                        context,
                        small: AppSpacing.md,
                        medium: AppSpacing.lg,
                      ),
                      vertical: AppSpacing.sm,
                    ),
                    itemCount: products.length,
                    itemBuilder: (context, index) {
                      final product = products[index];
                      // Load more on scroll near end
                      if (index == products.length - 5) {
                        unawaited(
                          Future.microtask(
                            () => ref
                                .read(catalogListProvider.notifier)
                                .loadMore(),
                          ),
                        );
                      }

                      final isOutOfStock =
                          product.currentStock != null &&
                          product.currentStock! <= 0;

                      return Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.md),
                        child: AppCard(
                          onTap: () => _openProductForm(productId: product.id),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Expanded(
                                    child: Text(
                                      product.name,
                                      style: AppTypography.titleMedium,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  const SizedBox(width: AppSpacing.md),
                                  AmountDisplay(
                                    amount: product.unitPrice,
                                    size: AmountSize.medium,
                                  ),
                                ],
                              ),
                              if (product.barcode != null) ...[
                                const SizedBox(height: AppSpacing.sm),
                                Text(
                                  'Code: ${product.barcode}',
                                  style: AppTypography.bodySmall,
                                ),
                              ],
                              if (product.currentStock != null) ...[
                                const SizedBox(height: AppSpacing.sm),
                                Text(
                                  'Stock: ${product.currentStock}',
                                  style: AppTypography.bodySmall,
                                ),
                              ],
                              const SizedBox(height: AppSpacing.md),
                              ElevatedButton(
                                onPressed: isOutOfStock
                                    ? null
                                    : () {
                                        ref
                                            .read(cartProvider.notifier)
                                            .addItem(product);
                                        ScaffoldMessenger.of(
                                          context,
                                        ).showSnackBar(
                                          SnackBar(
                                            content: Text(
                                              '${product.name} ajouté au panier',
                                            ),
                                            duration: const Duration(
                                              milliseconds: 1500,
                                            ),
                                          ),
                                        );
                                      },
                                child: Text(
                                  isOutOfStock
                                      ? 'Rupture'
                                      : 'Ajouter au panier',
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                );
              },
            ),
          ),
            ],
          ),
          // Cart floating button (bottom-right)
          if (!cartState.isEmpty)
            Positioned(
              bottom: AppSpacing.lg,
              right: AppSpacing.lg,
              child: FloatingActionButton.extended(
                backgroundColor: const Color(0xFF6B8E6F),
                onPressed: () => context.push(Routes.newSale),
                icon: const Icon(
                  Icons.shopping_cart,
                  color: AppColors.textOnPrimary,
                ),
                label: Text(
                  'Panier (${cartState.itemCount})',
                  style: const TextStyle(
                    color: AppColors.textOnPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
