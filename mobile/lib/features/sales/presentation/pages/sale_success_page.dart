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
import '../../../../shared/providers/connectivity_provider.dart';
import '../../domain/entities/sale.dart';
import '../../domain/entities/cart_item.dart';
import '../../../printing/domain/repositories/printer_repository.dart';
import '../../../printing/presentation/providers/printer_provider.dart';

/// SaleSuccessPage — confirmation screen after successful sale.
class SaleSuccessPage extends ConsumerWidget {
  /// Creates a [SaleSuccessPage].
  const SaleSuccessPage({required this.sale, required this.items, super.key});

  /// The sale that was just created.
  final Sale sale;

  /// The items in the sale.
  final List<CartItem> items;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isOnlineAsync = ref.watch(isOnlineProvider);
    final isOnline = isOnlineAsync.when(
      data: (v) => v,
      loading: () => true,
      error: (_, _) => false,
    );

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
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
              const SizedBox(height: AppSpacing.xxxl),
              // Success icon
              Center(
                child: Container(
                  width: 120,
                  height: 120,
                  decoration: BoxDecoration(
                    color: AppColors.successContainer,
                    borderRadius: BorderRadius.circular(60),
                  ),
                  child: const Icon(
                    Icons.check,
                    color: AppColors.success,
                    size: 64,
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              // Title
              const Text(
                'Vente enregistrée',
                style: AppTypography.displayMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.md),
              // Message
              Text(
                'La transaction a été complétée avec succès',
                style: AppTypography.bodyMedium.copyWith(
                  color: AppColors.textSecondary,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.xl),
              // Summary card
              AppCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Montant', style: AppTypography.bodyMedium),
                        AmountDisplay(
                          amount: sale.totalAmount,
                          size: AmountSize.large,
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Mode de paiement',
                          style: AppTypography.bodyMedium,
                        ),
                        Text(
                          _paymentMethodLabel(sale.paymentMethod),
                          style: AppTypography.labelMedium,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              // Offline message
              if (!isOnline)
                Container(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: BoxDecoration(
                    color: AppColors.warningContainer,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                    border: Border.all(color: AppColors.warning, width: 1),
                  ),
                  child: const Row(
                    children: [
                      Icon(Icons.cloud_off, color: AppColors.warning),
                      SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Text(
                          'Hors ligne. La vente sera envoyée au serveur au retour du réseau.',
                          style: AppTypography.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: AppSpacing.xl),
              // Actions
              PrimaryButton(
                label: 'Imprimer le reçu',
                onPressed: () => _printReceipt(context, ref),
                icon: Icons.print,
              ),
              const SizedBox(height: AppSpacing.md),
              SecondaryButton(
                label: 'Nouvelle vente',
                onPressed: () {
                  context.go(Routes.newSale);
                },
                icon: Icons.add_shopping_cart,
              ),
              const SizedBox(height: AppSpacing.md),
              TextButton(
                onPressed: () => context.go(Routes.home),
                child: const Text('Retour à l\'accueil'),
              ),
              const SizedBox(height: AppSpacing.xxxl),
            ],
          ),
        ),
      ),
    );
  }

  static String _paymentMethodLabel(PaymentMethod method) {
    return switch (method) {
      PaymentMethod.cash => 'Espèces',
      PaymentMethod.orangeMoney => 'Orange Money',
      PaymentMethod.mtn => 'MTN',
      PaymentMethod.wave => 'Wave',
      PaymentMethod.mixed => 'Mixte',
    };
  }

  Future<void> _printReceipt(BuildContext context, WidgetRef ref) async {
    try {
      await ref.read(printerProvider.notifier).print(sale: sale, items: items);
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Reçu imprimé')));
      }
    } on PrintException catch (e) {
      if (context.mounted) {
        if (e.reason == PrintFailureReason.noPrinterConfigured) {
          unawaited(context.push(Routes.bluetoothSetup));
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Erreur impression: ${e.details}'),
              backgroundColor: AppColors.error,
            ),
          );
        }
      }
    }
  }
}
