import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
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
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Text(dateLabel),
          ),
          // Sales list
          Expanded(
            child: salesAsync.when(
              loading: () => const AppLoadingIndicator(),
              error: (err, stack) => EmptyState(
                icon: Icons.error_outline,
                title: 'Erreur',
                message: err.toString(),
              ),
              data: (sales) {
                if (sales.isEmpty) {
                  return EmptyState(
                    icon: Icons.receipt_long_outlined,
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
                  separatorBuilder: (_, __) =>
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
    final timeLabel = DateFormat('HH:mm', 'fr_FR').format(sale.createdAt);
    final receiptLabel = sale.receiptNumber > 0
        ? '#${sale.receiptNumber}'
        : 'Provisoire';
    final paymentLabel = _paymentMethodLabel(sale.paymentMethod);
    final paymentColor = _paymentMethodColor(sale.paymentMethod);

    return AppCard(
      onTap: () => context.push(Routes.saleDetail, extra: sale),
      child: ListTile(
        leading: Icon(Icons.receipt_outlined, color: AppColors.primary),
        title: Text(receiptLabel),
        subtitle: Text('$timeLabel • $paymentLabel'),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              _formatAmount(sale.totalAmount),
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            Chip(
              label: Text(paymentLabel, style: const TextStyle(fontSize: 11)),
              backgroundColor: paymentColor,
              materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
          ],
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

  static Color _paymentMethodColor(PaymentMethod method) {
    return switch (method) {
      PaymentMethod.cash => AppColors.secondaryContainer,
      PaymentMethod.orangeMoney => const Color(0xFFFFE5D9),
      PaymentMethod.mtn => const Color(0xFFFFFDD0),
      PaymentMethod.wave => const Color(0xFFD6EFFF),
      PaymentMethod.mixed => AppColors.primaryContainer,
    };
  }

  static String _formatAmount(Decimal amount) {
    return '${(amount / Decimal.fromInt(1000)).toDouble().toStringAsFixed(0)}k FCFA';
  }
}
