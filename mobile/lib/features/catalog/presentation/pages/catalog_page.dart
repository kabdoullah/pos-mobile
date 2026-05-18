import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/catalog_providers.dart';

class CatalogPage extends ConsumerStatefulWidget {
  const CatalogPage({super.key});

  @override
  ConsumerState<CatalogPage> createState() => _CatalogPageState();
}

class _CatalogPageState extends ConsumerState<CatalogPage> {
  late TextEditingController _searchController;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    if (_debounce?.isActive ?? false) _debounce!.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      if (mounted) {
        ref.read(catalogListProvider.notifier).search(query);
      }
    });
  }

  Future<void> _onRefresh() async {
    await ref.read(catalogListProvider.notifier).refresh();
  }

  void _openProductForm({String? productId}) {
    if (productId == null) {
      context.push(Routes.productNew);
    } else {
      context.push(Routes.productEdit.replaceFirst(':id', productId));
    }
  }

  @override
  Widget build(BuildContext context) {
    final catalogState = ref.watch(catalogListProvider);

    return AppScaffold(
      title: 'Catalogue',
      floatingActionButton: FloatingActionButton(
        backgroundColor: AppColors.primary,
        onPressed: _openProductForm,
        child: const Icon(Icons.add, color: AppColors.textOnPrimary),
      ),
      body: Column(
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
            child: AppTextField(
              label: 'Rechercher',
              hint: 'Nom du produit...',
              controller: _searchController,
              prefixIcon: Icons.search,
              onChanged: _onSearchChanged,
            ),
          ),
          // Product list
          Expanded(
            child: catalogState.when(
              loading: () => const AppLoadingScreen(),
              error: (error, stack) => Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.error_outline, size: 48, color: AppColors.error),
                    const SizedBox(height: AppSpacing.md),
                    Text(
                      'Erreur: $error',
                      style: AppTypography.bodySmall,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
              data: (products) {
                if (products.isEmpty) {
                  return EmptyState(
                    icon: Icons.shopping_bag_outlined,
                    title: 'Aucun produit',
                    message: 'Commencez par ajouter votre premier produit',
                    actionLabel: 'Ajouter un produit',
                    onAction: _openProductForm,
                  );
                }

                return RefreshIndicator(
                  onRefresh: _onRefresh,
                  color: AppColors.primary,
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
                        Future.microtask(
                          () =>
                              ref.read(catalogListProvider.notifier).loadMore(),
                        );
                      }

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
    );
  }
}
