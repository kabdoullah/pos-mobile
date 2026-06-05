import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../../catalog/domain/entities/product.dart';
import '../../../catalog/presentation/providers/catalog_providers.dart';
import '../providers/cart_provider.dart';

/// AddProductToCartSheet — bottom sheet for searching and adding products.
class AddProductToCartSheet extends ConsumerStatefulWidget {
  /// Creates an [AddProductToCartSheet].
  const AddProductToCartSheet({super.key});

  @override
  ConsumerState<AddProductToCartSheet> createState() =>
      _AddProductToCartSheetState();
}

class _AddProductToCartSheetState extends ConsumerState<AddProductToCartSheet> {
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
    _debounce = Timer(const Duration(milliseconds: 300), () async {
      if (mounted) {
        await ref.read(catalogListProvider.notifier).search(query);
      }
    });
  }

  void _addToCart(Product product) {
    ref.read(cartProvider.notifier).addItem(product);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final catalogState = ref.watch(catalogListProvider);
    final spacing = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );

    return DraggableScrollableSheet(
      initialChildSize: 0.9,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      builder: (context, scrollController) {
        return Container(
          decoration: const BoxDecoration(
            color: AppColors.background,
            borderRadius: BorderRadius.vertical(
              top: Radius.circular(AppSpacing.radiusLg),
            ),
          ),
          child: Column(
            children: [
              // Handle
              Padding(
                padding: const EdgeInsets.only(top: AppSpacing.md),
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppColors.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Padding(
                padding: EdgeInsets.only(
                  left: spacing,
                  right: spacing,
                  top: spacing,
                  bottom: spacing + MediaQuery.of(context).viewInsets.bottom,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Ajouter un produit',
                      style: AppTypography.titleLarge,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AppTextField(
                      label: 'Rechercher',
                      hint: 'Nom du produit...',
                      controller: _searchController,
                      prefixIcon: Icons.search,
                      onChanged: _onSearchChanged,
                    ),
                  ],
                ),
              ),
              Expanded(
                child: catalogState.when(
                  loading: () => const AppLoadingScreen(),
                  error: (error, stack) => EmptyState(
                    icon: Icons.error_outline,
                    title: 'Impossible de charger',
                    message: 'Une erreur est survenue',
                    actionLabel: 'Réessayer',
                    onAction: () =>
                        ref.read(catalogListProvider.notifier).refresh(),
                  ),
                  data: (products) {
                    if (products.isEmpty) {
                      return const Center(
                        child: Text(
                          'Aucun produit',
                          style: AppTypography.bodyMedium,
                        ),
                      );
                    }

                    return ListView.builder(
                      controller: scrollController,
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
                        return Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.md),
                          child: AppCard(
                            onTap: () => _addToCart(product),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        product.name,
                                        style: AppTypography.titleMedium,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                      const SizedBox(height: AppSpacing.xs),
                                      AmountDisplay(
                                        amount: product.unitPrice,
                                        size: AmountSize.small,
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: AppSpacing.md),
                                Container(
                                  padding: const EdgeInsets.all(AppSpacing.sm),
                                  decoration: BoxDecoration(
                                    color: AppColors.primaryContainer,
                                    borderRadius: BorderRadius.circular(
                                      AppSpacing.radiusSm,
                                    ),
                                  ),
                                  child: const Icon(
                                    Icons.add,
                                    color: AppColors.primary,
                                    size: 20,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
