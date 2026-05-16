import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../../catalog/presentation/providers/catalog_providers.dart';
import '../providers/cart_provider.dart';
import 'add_product_to_cart_sheet.dart';

/// NewSalePage — shopping cart with scanner and quick checkout.
class NewSalePage extends ConsumerWidget {
  const NewSalePage({super.key});

  Future<void> _openScanner(BuildContext context, WidgetRef ref) async {
    final code = await context.push<String>(Routes.barcodeScanner);
    if (code != null) {
      // TODO: Look up product by barcode from catalog
      // For now, show feedback
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Scanné: $code')));
    }
  }

  void _showAddProductSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (context) => const AddProductToCartSheet(),
    );
  }

  void _checkout(BuildContext context) {
    context.push(Routes.payment);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cartState = ref.watch(cartProvider);

    return AppScaffold(
      title: 'Nouvelle vente',
      body: Column(
        children: [
          // Scanner & manual add buttons
          Padding(
            padding: EdgeInsets.all(
              responsiveValue(
                context,
                small: AppSpacing.md,
                medium: AppSpacing.lg,
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: PrimaryButton(
                    label: 'Scanner',
                    onPressed: () => _openScanner(context, ref),
                    icon: Icons.qr_code_2,
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: SecondaryButton(
                    label: 'Ajouter',
                    onPressed: () => _showAddProductSheet(context),
                    icon: Icons.add_shopping_cart,
                  ),
                ),
              ],
            ),
          ),
          // Cart items
          Expanded(
            child: cartState.isEmpty
                ? EmptyState(
                    icon: Icons.shopping_cart_outlined,
                    title: 'Panier vide',
                    message: 'Scannez des produits ou ajoutez-les manuellement',
                    actionLabel: 'Ajouter un produit',
                    onAction: () => _showAddProductSheet(context),
                  )
                : ListView.builder(
                    padding: EdgeInsets.symmetric(
                      horizontal: responsiveValue(
                        context,
                        small: AppSpacing.md,
                        medium: AppSpacing.lg,
                      ),
                      vertical: AppSpacing.sm,
                    ),
                    itemCount: cartState.items.length,
                    itemBuilder: (context, index) {
                      final item = cartState.items[index];
                      return Dismissible(
                        key: ValueKey(item.productId),
                        direction: DismissDirection.endToStart,
                        onDismissed: (_) {
                          ref
                              .read(cartProvider.notifier)
                              .removeItem(item.productId);
                        },
                        background: Container(
                          color: AppColors.error,
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: AppSpacing.md),
                          child: const Icon(
                            Icons.delete,
                            color: AppColors.textOnPrimary,
                          ),
                        ),
                        child: AppCard(
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.center,
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      item.productName,
                                      style: AppTypography.titleMedium,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    const SizedBox(height: AppSpacing.xs),
                                    Text(
                                      '${item.quantity} x ${AmountDisplay(amount: int.parse(item.unitPrice), size: AmountSize.small).build(context)}',
                                      style: AppTypography.bodySmall,
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: AppSpacing.md),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  AmountDisplay(
                                    amount: item.lineTotal,
                                    size: AmountSize.large,
                                  ),
                                  const SizedBox(height: AppSpacing.xs),
                                  Row(
                                    children: [
                                      GestureDetector(
                                        onTap: () => ref
                                            .read(cartProvider.notifier)
                                            .updateQuantity(
                                              item.productId,
                                              item.quantity - 1,
                                            ),
                                        child: Container(
                                          width: 32,
                                          height: 32,
                                          decoration: BoxDecoration(
                                            color: AppColors.primaryContainer,
                                            borderRadius: BorderRadius.circular(
                                              AppSpacing.radiusSm,
                                            ),
                                          ),
                                          child: const Icon(
                                            Icons.remove,
                                            size: 16,
                                            color: AppColors.primary,
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: AppSpacing.xs),
                                      GestureDetector(
                                        onTap: () => ref
                                            .read(cartProvider.notifier)
                                            .updateQuantity(
                                              item.productId,
                                              item.quantity + 1,
                                            ),
                                        child: Container(
                                          width: 32,
                                          height: 32,
                                          decoration: BoxDecoration(
                                            color: AppColors.primaryContainer,
                                            borderRadius: BorderRadius.circular(
                                              AppSpacing.radiusSm,
                                            ),
                                          ),
                                          child: const Icon(
                                            Icons.add,
                                            size: 16,
                                            color: AppColors.primary,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
          // Total & checkout
          Container(
            color: AppColors.surface,
            padding: EdgeInsets.all(
              responsiveValue(
                context,
                small: AppSpacing.md,
                medium: AppSpacing.lg,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Total', style: AppTypography.titleMedium),
                    AmountDisplay(
                      amount: cartState.total,
                      size: AmountSize.hero,
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.lg),
                PrimaryButton(
                  label: 'Encaisser',
                  onPressed: cartState.isEmpty
                      ? null
                      : () => _checkout(context),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
