import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/sync/sync_orchestrator.dart';
import '../../../../core/theme/app_colors.dart';
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
    final syncStatus = ref.watch(syncOrchestratorProvider);
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
          // Sync status indicator
          if (syncStatus is SyncStatusError)
            Builder(
              builder: (context) {
                final cs = Theme.of(context).colorScheme;
                return Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  color: cs.errorContainer,
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: cs.error, size: 18),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: Text(
                          syncStatus.message,
                          style: Theme.of(
                            context,
                          ).textTheme.bodySmall?.copyWith(color: cs.error),
                        ),
                      ),
                    ],
                  ),
                );
              },
            )
          else if (syncStatus is SyncStatusSyncing)
            Builder(
              builder: (context) {
                final cs = Theme.of(context).colorScheme;
                return Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  color: cs.primaryContainer,
                  child: Row(
                    children: [
                      SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(cs.primary),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Text(
                        'Synchronisation en cours...',
                        style: Theme.of(
                          context,
                        ).textTheme.bodySmall?.copyWith(color: cs.primary),
                      ),
                    ],
                  ),
                );
              },
            ),
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
    final brightness = Theme.of(context).brightness;
    final timeLabel = DateFormat('HH:mm', 'fr_FR').format(sale.createdAt);
    final receiptLabel = sale.receiptNumber > 0
        ? '#${sale.receiptNumber}'
        : 'Provisoire';
    final paymentLabel = _paymentMethodLabel(sale.paymentMethod);
    final paymentColor = _paymentMethodColor(
      sale.paymentMethod,
      cs,
      brightness,
    );

    return AppCard(
      onTap: () => context.push(Routes.saleDetail, extra: sale),
      child: ListTile(
        leading: Icon(Icons.receipt_outlined, color: cs.primary),
        title: Text(receiptLabel),
        subtitle: Text('$timeLabel • $paymentLabel'),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              _formatAmount(sale.totalAmount),
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
            ),
            Chip(
              label: Text(
                paymentLabel,
                style: Theme.of(context).textTheme.labelSmall,
              ),
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

  static Color _paymentMethodColor(
    PaymentMethod method,
    ColorScheme cs,
    Brightness brightness,
  ) {
    return switch (method) {
      PaymentMethod.cash => cs.secondaryContainer,
      PaymentMethod.orangeMoney => AppColors.orangeMoneyBg(brightness),
      PaymentMethod.mtn => AppColors.mtnBg(brightness),
      PaymentMethod.wave => AppColors.waveBg(brightness),
      PaymentMethod.mixed => cs.primaryContainer,
    };
  }

  static String _formatAmount(Decimal amount) {
    return '${NumberFormat('#,##0', 'fr_FR').format(amount.toDouble())} FCFA';
  }
}
