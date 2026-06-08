import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/navigation/nav_provider.dart';
import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../../auth/providers/store_provider.dart';
import '../providers/home_providers.dart';

/// Premium financial dashboard with asymmetric layout and refined aesthetics.
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
    final hPad = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );

    return AppScaffold(
      title: storeName,
      actions: [
        IconButton(
          icon: const Icon(Icons.settings_outlined),
          onPressed: () =>
              ref.read(bottomNavIndexProvider.notifier).setIndex(3),
          tooltip: 'Paramètres',
        ),
      ],
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: store name + date
            Padding(
              padding: EdgeInsets.fromLTRB(
                hPad,
                AppSpacing.lg,
                hPad,
                AppSpacing.xl,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    dateLabel,
                    style: AppTypography.bodySmall.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),

            // Daily summary card
            Padding(
              padding: EdgeInsets.symmetric(horizontal: hPad),
              child: dailySummaryAsync.when(
                loading: () => const AppLoadingIndicator(),
                error: (_, _) => _SummaryCard(
                  summary: DailySummary.empty,
                  hasError: true,
                  onRetry: () => ref.invalidate(dailySummaryProvider),
                ),
                data: (summary) => _SummaryCard(summary: summary),
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            Padding(
              padding: EdgeInsets.symmetric(horizontal: hPad),
              child: SizedBox(
                width: double.infinity,
                height: AppSpacing.buttonHeight,
                child: FilledButton.icon(
                  onPressed: () => context.push(Routes.newSale),
                  icon: const Icon(Icons.point_of_sale, size: 22),
                  label: const Text('NOUVELLE VENTE'),
                  style: FilledButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                    ),
                    textStyle: AppTypography.labelLarge.copyWith(
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.8,
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            const _QuickActionsSection(),
            const SizedBox(height: AppSpacing.xl),
          ],
        ),
      ),
    );
  }
}

/// Quick access section for frequent POS operations.
class _QuickActionsSection extends ConsumerWidget {
  const _QuickActionsSection();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final hPad = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: hPad),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Accès rapide',
            style: AppTypography.labelMedium.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          // ✨ IntrinsicHeight + stretch — toutes les cartes à la même hauteur
          // quelle que soit la longueur du label (ex: "Nouveau produit" sur 2 lignes)
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(
                  child: _QuickActionCard(
                    icon: Icons.shopping_bag_outlined,
                    label: 'Catalogue',
                    onTap: () =>
                        ref.read(bottomNavIndexProvider.notifier).setIndex(1),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: _QuickActionCard(
                    icon: Icons.history_outlined,
                    label: 'Historique',
                    onTap: () =>
                        ref.read(bottomNavIndexProvider.notifier).setIndex(2),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: _QuickActionCard(
                    icon: Icons.add_box_outlined,
                    label: 'Nouveau produit',
                    onTap: () => context.push(Routes.productNew),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Tappable quick-action card with icon and label.
class _QuickActionCard extends StatelessWidget {
  const _QuickActionCard({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return AppCard(
      onTap: onTap,
      padding: AppSpacing.md,
      child: Column(
        // ✨ mainAxisAlignment center — contenu centré quand la carte s'étire
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: cs.primaryContainer,
              borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
            ),
            child: Icon(icon, color: cs.onPrimaryContainer, size: 22),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            label,
            textAlign: TextAlign.center,
            style: AppTypography.labelSmall.copyWith(
              color: cs.onSurface,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

/// Premium summary card with gradient background.
class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.summary,
    this.hasError = false,
    this.onRetry,
  });

  final DailySummary summary;

  /// When true, shows a subtle error indicator at the bottom of the card.
  final bool hasError;

  /// Optional retry callback shown when [hasError] is true.
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(
      context,
    ).textTheme; // ✨ un seul lookup pour l'error block
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            cs.primary.withValues(alpha: 0.95),
            cs.primary.withValues(alpha: 0.85),
          ],
        ),
        borderRadius: BorderRadius.circular(AppSpacing.radiusXl),
        boxShadow: [
          BoxShadow(
            color: cs.primary.withValues(alpha: 0.2),
            blurRadius: 30,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Total du jour',
              style: AppTypography.labelMedium.copyWith(
                color: cs.onPrimary.withValues(alpha: 0.8),
                fontWeight: FontWeight.w500,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            AmountDisplay(
              amount: summary.totalAmount,
              size: AmountSize.hero,
              color: cs.onPrimary,
            ),
            const SizedBox(height: AppSpacing.xl),
            Row(
              children: [
                _SummaryMetric(
                  label: 'Nombre',
                  child: Text(
                    '${summary.saleCount}',
                    style: AppTypography.bodyLarge.copyWith(
                      color: cs.onPrimary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                _SummaryMetric(
                  label: 'Espèces',
                  child: AmountDisplay(
                    amount: summary.cashTotal,
                    size: AmountSize.medium,
                    color: cs.onPrimary,
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                _SummaryMetric(
                  label: 'Mobile',
                  child: AmountDisplay(
                    amount: summary.mobileMoneyTotal,
                    size: AmountSize.medium,
                    color: cs.onPrimary,
                  ),
                ),
              ],
            ),
            if (hasError) ...[
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  Icon(
                    Icons.warning_outlined,
                    color: cs.onPrimary.withValues(alpha: 0.7),
                    size: 14,
                  ),
                  const SizedBox(width: AppSpacing.xs),
                  Text(
                    'Données non disponibles',
                    style: tt.labelSmall?.copyWith(
                      color: cs.onPrimary.withValues(alpha: 0.7),
                    ),
                  ),
                  if (onRetry != null) ...[
                    const SizedBox(width: AppSpacing.sm),
                    // ✨ TextButton : ripple + zone tactile 48px + Semantics natifs
                    TextButton(
                      onPressed: onRetry,
                      style: TextButton.styleFrom(
                        foregroundColor: cs.onPrimary,
                        padding: EdgeInsets.zero,
                        minimumSize: const Size(48, 32),
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        textStyle: tt.labelSmall?.copyWith(
                          decoration: TextDecoration.underline,
                          decorationColor: cs.onPrimary,
                        ),
                      ),
                      child: const Text('Réessayer'),
                    ),
                  ],
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Labeled metric in the summary card.
class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric({required this.label, required this.child});

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    // ✨ extrait pour éviter Theme.of(context) multi-ligne verbeux
    final cs = Theme.of(context).colorScheme;
    return Expanded(
      child: Column(
        children: [
          Text(
            label,
            style: AppTypography.captionText.copyWith(
              color: cs.onPrimary.withValues(alpha: 0.7),
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          child,
        ],
      ),
    );
  }
}
