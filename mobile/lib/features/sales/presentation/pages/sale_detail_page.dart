import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../domain/entities/sale.dart';
import '../../../printing/presentation/providers/printer_provider.dart';
import '../../../printing/domain/repositories/printer_repository.dart';

/// Sale detail page — read-only view of a completed sale.
///
/// Receives [Sale] via GoRouter extra — not by ID lookup.
/// Items are not available outside the originating session.
class SaleDetailPage extends ConsumerWidget {
  /// Creates a [SaleDetailPage].
  const SaleDetailPage({required this.sale, super.key});

  /// The sale to display.
  final Sale sale;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dateFormatter = DateFormat('EEEE d MMMM yyyy HH:mm', 'fr_FR');
    final receiptNumber = sale.receiptNumber > 0
        ? '#${sale.receiptNumber}'
        : 'Provisoire';

    return AppScaffold(
      title: 'Vente $receiptNumber',
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Header card with sale info
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Reçu N°', style: AppTypography.captionText),
                          const SizedBox(height: AppSpacing.xs),
                          Text(receiptNumber, style: AppTypography.titleLarge),
                        ],
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          const Text(
                            'Mode de paiement',
                            style: AppTypography.captionText,
                          ),
                          const SizedBox(height: AppSpacing.xs),
                          Text(
                            _paymentMethodLabel(sale.paymentMethod),
                            style: AppTypography.labelLarge,
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Text(
                    dateFormatter.format(sale.createdAt),
                    style: AppTypography.bodySmall,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  const Divider(),
                  const SizedBox(height: AppSpacing.md),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Montant total', style: AppTypography.captionText),
                      const SizedBox(height: AppSpacing.xs),
                      AmountDisplay(
                        amount: sale.totalAmount,
                        size: AmountSize.large,
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Warning card about items not available
            AppCard(
              child: Container(
                decoration: BoxDecoration(
                  color: AppColors.warningContainer,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                ),
                padding: const EdgeInsets.all(AppSpacing.md),
                child: const Row(
                  children: [
                    Icon(Icons.info_outline, color: AppColors.warning),
                    SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Text(
                        'Le détail des articles n\'est disponible que pendant la session de vente.',
                        style: AppTypography.bodySmall,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // Reprint button
            PrimaryButton(
              label: 'Réimprimer le reçu',
              icon: Icons.print,
              onPressed: () => _handlePrint(context, ref),
            ),
          ],
        ),
      ),
    );
  }

  /// Handles printing the receipt.
  Future<void> _handlePrint(BuildContext context, WidgetRef ref) async {
    try {
      // Items are null when printing from history (not in session)
      await ref.read(printerProvider.notifier).print(sale: sale, items: null);

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Reçu imprimé avec succès'),
            backgroundColor: AppColors.secondary,
            duration: Duration(seconds: 2),
          ),
        );
      }
    } on PrintException catch (e) {
      if (context.mounted) {
        if (e.reason == PrintFailureReason.noPrinterConfigured) {
          // Navigate to printer setup if not configured
          // context.push(Routes.bluetoothSetup);
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text('Aucune imprimante configurée'),
              action: SnackBarAction(
                label: 'Configurer',
                onPressed: () {
                  // TODO: Navigate to bluetooth setup
                },
              ),
            ),
          );
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Erreur d\'impression: ${e.details}'),
              backgroundColor: AppColors.error,
            ),
          );
        }
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Erreur: ${e.toString()}'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
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
}
