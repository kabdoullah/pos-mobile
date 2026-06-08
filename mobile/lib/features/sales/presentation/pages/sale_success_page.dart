import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../../../shared/providers/connectivity_provider.dart';
import '../../domain/entities/sale.dart';
import '../../domain/entities/cart_item.dart';
import '../../../printing/domain/repositories/printer_repository.dart';
import '../../../printing/presentation/providers/printer_provider.dart';

/// SaleSuccessPage — confirmation screen after successful sale.
class SaleSuccessPage extends ConsumerStatefulWidget {
  /// Creates a [SaleSuccessPage].
  const SaleSuccessPage({required this.sale, required this.items, super.key});

  /// The sale that was just created.
  final Sale sale;

  /// The items in the sale.
  final List<CartItem> items;

  @override
  ConsumerState<SaleSuccessPage> createState() => _SaleSuccessPageState();
}

class _SaleSuccessPageState extends ConsumerState<SaleSuccessPage>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 500),
      vsync: this,
    );
    _scaleAnimation = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOutBack,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _controller,
      curve: const Interval(0.0, 0.6, curve: Curves.easeOut),
    );
    unawaited(_controller.forward());
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isOnlineAsync = ref.watch(isOnlineProvider);
    final isOnline = isOnlineAsync.when(
      data: (v) => v,
      loading: () => true,
      error: (_, _) => false,
    );

    return Scaffold(
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
              // ✨ ScaleTransition + FadeTransition — entrée animée "pop" satisfaisante
              Center(
                child: FadeTransition(
                  opacity: _fadeAnimation,
                  child: ScaleTransition(
                    scale: _scaleAnimation,
                    child: Container(
                      width: 120,
                      height: 120,
                      decoration: BoxDecoration(
                        color: cs.primaryContainer,
                        borderRadius: BorderRadius.circular(60),
                      ),
                      child: Icon(
                        Icons.check_rounded,
                        color: cs.primary,
                        size: 64,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              const Text(
                'Vente enregistrée',
                style: AppTypography.displayMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.md),
              Text(
                'La transaction a été complétée avec succès',
                // ✨ cs.onSurfaceVariant — dark-mode safe, remplace AppColors.textSecondary
                style: AppTypography.bodyMedium.copyWith(
                  color: cs.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.xl),
              AppCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Montant', style: AppTypography.bodyMedium),
                        AmountDisplay(
                          amount: widget.sale.totalAmount,
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
                          _paymentMethodLabel(widget.sale.paymentMethod),
                          style: AppTypography.labelMedium,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              // ✨ cs.tertiaryContainer + cs.onTertiaryContainer — offline banner dark-mode safe
              if (!isOnline)
                Container(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: BoxDecoration(
                    color: cs.tertiaryContainer,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                    border: Border.all(
                      color: cs.tertiary.withValues(alpha: 0.5),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.cloud_off, color: cs.onTertiaryContainer),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Text(
                          'Hors ligne. La vente sera envoyée au serveur au retour du réseau.',
                          style: AppTypography.bodySmall.copyWith(
                            color: cs.onTertiaryContainer,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: AppSpacing.xl),
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
      await ref
          .read(printerProvider.notifier)
          .print(sale: widget.sale, items: widget.items);
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
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
          );
        }
      }
    }
  }
}
