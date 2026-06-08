import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/illustrations.dart';
import '../../../../shared/widgets/index.dart';
import '../../domain/entities/sale.dart';
import '../providers/sales_providers.dart';

/// Sales history page — displays past sales with date filtering.
class SalesHistoryPage extends ConsumerStatefulWidget {
  /// Creates a [SalesHistoryPage].
  const SalesHistoryPage({super.key});

  @override
  ConsumerState<SalesHistoryPage> createState() => _SalesHistoryPageState();
}

class _SalesHistoryPageState extends ConsumerState<SalesHistoryPage> {
  late DateTime _selectedDate;

  @override
  void initState() {
    super.initState();
    _selectedDate = DateTime.now();
  }

  Future<void> _selectDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime.now().subtract(const Duration(days: 90)),
      lastDate: DateTime.now(),
    );
    if (picked != null && mounted) {
      setState(() => _selectedDate = picked);
    }
  }

  @override
  Widget build(BuildContext context) {
    final salesAsync = ref.watch(salesHistoryProvider(date: _selectedDate));
    final dateLabel = DateFormat('dd MMMM yyyy', 'fr_FR').format(_selectedDate);

    return AppScaffold(
      title: 'Historique des ventes',
      actions: [
        IconButton(
          icon: const Icon(Icons.calendar_today),
          onPressed: _selectDate,
          tooltip: 'Changer la date',
        ),
      ],
      body: Column(
        children: [
          // Date filter header
          Container(
            width: double.infinity,
            color: Theme.of(context).colorScheme.surfaceContainerLow,
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.sm,
            ),
            child: Text(
              dateLabel,
              style: Theme.of(context).textTheme.titleSmall,
              textAlign: TextAlign.center,
            ),
          ),
          // Sales list
          Expanded(
            child: salesAsync.when(
              loading: () => const AppLoadingScreen(),
              error: (err, stack) => const EmptyStateIllustrated(
                illustration: Illustrations.errorState,
                title: 'Erreur',
                message: 'Impossible de charger l\'historique',
              ),
              data: (sales) {
                if (sales.isEmpty) {
                  return const EmptyStateIllustrated(
                    illustration: Illustrations.emptySales,
                    title: 'Aucune vente',
                    message: 'Pas de vente enregistrée ce jour.',
                  );
                }
                return ListView.separated(
                  padding: EdgeInsets.all(
                    responsiveValue(
                      context,
                      small: AppSpacing.md,
                      medium: AppSpacing.lg,
                    ),
                  ),
                  itemCount: sales.length,
                  separatorBuilder: (_, _) =>
                      const SizedBox(height: AppSpacing.sm),
                  itemBuilder: (context, index) {
                    final sale = sales[index];
                    return _SaleCard(sale: sale);
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

/// Private sale card widget — displays a single sale in history.
class _SaleCard extends ConsumerWidget {
  /// Creates a [_SaleCard].
  const _SaleCard({required this.sale});

  /// The sale to display.
  final Sale sale;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cs = Theme.of(context).colorScheme;
    final timeLabel = DateFormat('HH:mm', 'fr_FR').format(sale.createdAt);
    final receiptLabel = sale.receiptNumber > 0
        ? '#${sale.receiptNumber}'
        : 'Provisoire';
    final paymentLabel = _paymentMethodLabel(sale.paymentMethod);

    return AppCard(
      onTap: () => context.push(Routes.saleDetail, extra: sale),
      child: ListTile(
        leading: Icon(Icons.receipt_outlined, color: cs.primary),
        title: Text(receiptLabel),
        subtitle: Text('$timeLabel • $paymentLabel'),
        // ✨ amount seul — paymentLabel déjà dans subtitle, chip supprimé (redondant)
        trailing: AmountDisplay(
          amount: sale.totalAmount,
          size: AmountSize.small,
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.xs,
        ),
      ),
    );
  }

  static String _paymentMethodLabel(PaymentMethod method) {
    return switch (method) {
      PaymentMethod.cash => 'Espèces',
      PaymentMethod.orangeMoney => 'Orange',
      PaymentMethod.mtn => 'MTN',
      PaymentMethod.wave => 'Wave',
      PaymentMethod.mixed => 'Mixte',
    };
  }
}
