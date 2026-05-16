import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../../auth/presentation/providers/store_provider.dart';
import '../providers/home_providers.dart';

/// Home page — dashboard with today's sales summary and quick access.
class HomePage extends ConsumerWidget {
  /// Creates a [HomePage].
  const HomePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dailySummaryAsync = ref.watch(dailySummaryProvider);
    final storeAsync = ref.watch(storeConfigProvider);

    final storeName =
        storeAsync.whenOrNull(data: (s) => s?.name) ?? 'Ma boutique';
    final dateLabel = DateFormat('EEEE d MMMM', 'fr_FR').format(DateTime.now());

    return AppScaffold(
      title: 'Bonjour',
      actions: [
        IconButton(
          icon: const Icon(Icons.settings_outlined),
          onPressed: () => context.push(Routes.settings),
          tooltip: 'Paramètres',
        ),
      ],
      body: SingleChildScrollView(
        padding: EdgeInsets.all(
          responsiveValue(context, small: AppSpacing.md, medium: AppSpacing.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Store name + date header
            Text(storeName, style: AppTypography.titleLarge),
            const SizedBox(height: AppSpacing.xs),
            Text(dateLabel, style: AppTypography.bodySmall),
            const SizedBox(height: AppSpacing.lg),

            // Hero summary card
            dailySummaryAsync.when(
              loading: () => const AppLoadingIndicator(),
              error: (_, __) => const _SummaryCard(summary: DailySummary.empty),
              data: (summary) => _SummaryCard(summary: summary),
            ),
            const SizedBox(height: AppSpacing.lg),

            // NOUVELLE VENTE — primary CTA
            PrimaryButton(
              label: 'NOUVELLE VENTE',
              onPressed: () => context.push(Routes.newSale),
              icon: Icons.point_of_sale,
            ),
            const SizedBox(height: AppSpacing.xl),

            // Quick access row
            Row(
              children: [
                Expanded(
                  child: _QuickCard(
                    icon: Icons.shopping_bag_outlined,
                    label: 'Catalogue',
                    onTap: () => context.push(Routes.catalog),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: _QuickCard(
                    icon: Icons.history,
                    label: 'Historique',
                    onTap: () => context.push(Routes.salesHistory),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: _QuickCard(
                    icon: Icons.settings_outlined,
                    label: 'Paramètres',
                    onTap: () => context.push(Routes.settings),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Private summary card widget — shows today's totals and breakdown.
class _SummaryCard extends StatelessWidget {
  /// Creates a [_SummaryCard].
  const _SummaryCard({required this.summary});

  /// The summary data to display.
  final DailySummary summary;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AmountDisplay(amount: summary.totalAmount, size: AmountSize.hero),
          const SizedBox(height: AppSpacing.md),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _SummaryItem(label: 'Nombre', value: '${summary.saleCount}'),
              _SummaryItem(
                label: 'Espèces',
                value: AmountDisplay(
                  amount: summary.cashTotal,
                  size: AmountSize.medium,
                ),
              ),
              _SummaryItem(
                label: 'Mobile',
                value: AmountDisplay(
                  amount: summary.mobileMoneyTotal,
                  size: AmountSize.medium,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Private summary item widget — shows a label and value.
class _SummaryItem extends StatelessWidget {
  /// Creates a [_SummaryItem].
  const _SummaryItem({required this.label, required this.value});

  /// Item label.
  final String label;

  /// Item value (string or widget).
  final dynamic value;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          label,
          style: AppTypography.captionText,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: AppSpacing.xs),
        if (value is String)
          Text(
            value as String,
            style: AppTypography.bodyLarge,
            textAlign: TextAlign.center,
          )
        else
          value as Widget,
      ],
    );
  }
}

/// Private quick access card widget.
class _QuickCard extends StatelessWidget {
  /// Creates a [_QuickCard].
  const _QuickCard({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  /// Card icon.
  final IconData icon;

  /// Card label.
  final String label;

  /// On tap callback.
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      padding: AppSpacing.md,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 32, color: AppColors.primary),
          const SizedBox(height: AppSpacing.sm),
          Text(
            label,
            style: AppTypography.labelMedium,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
