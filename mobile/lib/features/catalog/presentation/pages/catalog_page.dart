import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/sync/sync_orchestrator.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/theme/illustrations.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/catalog_providers.dart';

/// Displays the product catalogue with search, refresh, and navigation
/// to product creation or editing screens.
class CatalogPage extends ConsumerStatefulWidget {
  /// Creates a [CatalogPage].
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
    ref.read(catalogListProvider.notifier).setSearchQuery(query);
  }

  Future<void> _onRefresh() async {
    await ref
        .read(syncOrchestratorProvider.notifier)
        .syncNow(forceFullPull: true);
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
    final catalogState = ref.watch(catalogListProvider);
    final cs = Theme.of(context).colorScheme;

    return AppScaffold(
      title: 'Catalogue',
      floatingActionButton: FloatingActionButton(
        onPressed: _openProductForm,
        tooltip: 'Ajouter un produit',
        child: const Icon(Icons.add),
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
            child: Container(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                boxShadow: [
                  BoxShadow(
                    // ✨ cs.primary — dark-mode aware, remplace AppColors.primary hardcodé
                    color: cs.primary.withValues(alpha: 0.08),
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
                  // ✨ cs.primary / cs.primaryContainer — dark-mode aware
                  color: cs.primary,
                  backgroundColor: cs.primaryContainer,
                  strokeWidth: 3,
                  child: NotificationListener<ScrollNotification>(
                    onNotification: (notification) {
                      if (notification is ScrollEndNotification) {
                        final px = notification.metrics.pixels;
                        final max = notification.metrics.maxScrollExtent;
                        if (max > 0 && px >= max - 300) {
                          unawaited(
                            ref.read(catalogListProvider.notifier).loadMore(),
                          );
                        }
                      }
                      return false;
                    },
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
                                  // ✨ onSurfaceVariant — info secondaire hiérarchisée
                                  style: AppTypography.bodySmall.copyWith(
                                    color: cs.onSurfaceVariant,
                                  ),
                                ),
                              ],
                              if (product.currentStock != null) ...[
                                const SizedBox(height: AppSpacing.sm),
                                Text(
                                  'Stock: ${product.currentStock}',
                                  style: AppTypography.bodySmall.copyWith(
                                    color: cs.onSurfaceVariant,
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      );
                    },
                  ),
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
