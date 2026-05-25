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

const Color _textLight = Color(0xFF8A8A8A);

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
        child: Column(
          children: [
            // Header with store name and date
            Padding(
              padding: EdgeInsets.fromLTRB(
                responsiveValue(
                  context,
                  small: AppSpacing.md,
                  medium: AppSpacing.lg,
                ),
                AppSpacing.lg,
                responsiveValue(
                  context,
                  small: AppSpacing.md,
                  medium: AppSpacing.lg,
                ),
                AppSpacing.xl,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    storeName,
                    style: AppTypography.titleLarge.copyWith(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w700,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    dateLabel,
                    style: AppTypography.bodySmall.copyWith(
                      color: _textLight,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),

            // Main content area with asymmetric layout
            Padding(
              padding: EdgeInsets.symmetric(
                horizontal: responsiveValue(
                  context,
                  small: AppSpacing.md,
                  medium: AppSpacing.lg,
                ),
              ),
              child: Column(
                children: [
                  // Hero summary section
                  dailySummaryAsync.when(
                    loading: () => const AppLoadingIndicator(),
                    error: (_, _) => _SummaryCard(summary: DailySummary.empty),
                    data: (summary) => _SummaryCard(summary: summary),
                  ),
                  const SizedBox(height: AppSpacing.xl),

                  // Primary CTA — full width
                  GestureDetector(
                    onTap: () => context.push(Routes.newSale),
                    child: MouseRegion(
                      cursor: SystemMouseCursors.click,
                      child: AnimatedScale(
                        scale: 1.0,
                        duration: const Duration(milliseconds: 150),
                        child: Container(
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [
                                AppColors.primary,
                                AppColors.primary.withValues(alpha: 0.9),
                              ],
                            ),
                            borderRadius: BorderRadius.circular(
                              AppSpacing.radiusMd,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: AppColors.primary.withValues(
                                  alpha: 0.25,
                                ),
                                blurRadius: 20,
                                offset: const Offset(0, 8),
                              ),
                            ],
                          ),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              vertical: AppSpacing.lg,
                              horizontal: AppSpacing.md,
                            ),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(
                                  Icons.point_of_sale,
                                  color: AppColors.textOnPrimary,
                                  size: 22,
                                ),
                                const SizedBox(width: AppSpacing.sm),
                                Text(
                                  'NOUVELLE VENTE',
                                  style: AppTypography.labelLarge.copyWith(
                                    color: AppColors.textOnPrimary,
                                    fontWeight: FontWeight.w600,
                                    letterSpacing: 0.8,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xl),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Premium summary card with glass-morphism effect.
class _SummaryCard extends StatefulWidget {
  const _SummaryCard({required this.summary});
  final DailySummary summary;

  @override
  State<_SummaryCard> createState() => _SummaryCardState();
}

class _SummaryCardState extends State<_SummaryCard> {
  @override
  void initState() {
    super.initState();
    Future.delayed(const Duration(milliseconds: 50), () {
      if (mounted) setState(() {});
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.primary.withValues(alpha: 0.95),
            AppColors.primary.withValues(alpha: 0.85),
          ],
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withValues(alpha: 0.2),
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
            // Label
            Text(
              'Total du jour',
              style: AppTypography.labelMedium.copyWith(
                color: AppColors.textOnPrimary.withValues(alpha: 0.8),
                fontWeight: FontWeight.w500,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // Hero amount with serif font treatment
            AmountDisplay(
              amount: widget.summary.totalAmount,
              size: AmountSize.hero,
            ),
            const SizedBox(height: AppSpacing.xl),

            // Breakdown row with refined styling
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _SummaryMetric(
                  label: 'Nombre',
                  value: '${widget.summary.saleCount}',
                ),
                const SizedBox(width: AppSpacing.md),
                _SummaryMetric(
                  label: 'Espèces',
                  value: AmountDisplay(
                    amount: widget.summary.cashTotal,
                    size: AmountSize.medium,
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                _SummaryMetric(
                  label: 'Mobile',
                  value: AmountDisplay(
                    amount: widget.summary.mobileMoneyTotal,
                    size: AmountSize.medium,
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

/// Refined metric display for summary breakdown.
class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric({required this.label, required this.value});

  final String label;
  final dynamic value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            label,
            style: AppTypography.captionText.copyWith(
              color: AppColors.textOnPrimary.withValues(alpha: 0.7),
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          if (value is String)
            Text(
              value as String,
              style: AppTypography.bodyLarge.copyWith(
                color: AppColors.textOnPrimary,
                fontWeight: FontWeight.w600,
              ),
            )
          else
            value as Widget,
        ],
      ),
    );
  }
}
