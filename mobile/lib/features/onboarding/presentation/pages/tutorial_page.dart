import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';

/// Tutorial carousel for onboarding.
///
/// 4 slides introducing core features:
/// 1. Add products
/// 2. Make sales
/// 3. Print receipts
/// 4. View sales history
class TutorialPage extends StatefulWidget {
  /// Creates a tutorial page.
  const TutorialPage({super.key});

  @override
  State<TutorialPage> createState() => _TutorialPageState();
}

class _TutorialPageState extends State<TutorialPage> {
  late PageController _pageController;
  int _currentPage = 0;

  static const List<TutorialSlide> _slides = [
    TutorialSlide(
      title: 'Ajouter des produits',
      description: 'Gérez votre catalogue directement dans l\'app.',
      icon: Icons.shopping_bag_outlined,
    ),
    TutorialSlide(
      title: 'Faire une vente',
      description: 'Sélectionnez les articles et encaissez rapidement.',
      icon: Icons.point_of_sale_outlined,
    ),
    TutorialSlide(
      title: 'Imprimer le reçu',
      description: 'Connectez votre imprimante thermique sans fil.',
      icon: Icons.receipt_long_outlined,
    ),
    TutorialSlide(
      title: 'Consulter mes ventes',
      description: 'Suivez vos revenus en temps réel et hors ligne.',
      icon: Icons.trending_up_outlined,
      isAccent: true,
    ),
  ];

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _nextSlide() {
    if (_currentPage < _slides.length - 1) {
      unawaited(
        _pageController.nextPage(
          duration: const Duration(milliseconds: 400),
          curve: Curves.easeInOut,
        ),
      );
    } else {
      if (mounted) {
        context.go(Routes.home);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final padding = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            // Dismiss button
            Align(
              alignment: Alignment.topRight,
              child: Padding(
                padding: EdgeInsets.all(padding),
                child: TextButton.icon(
                  onPressed: () => context.go(Routes.home),
                  icon: Icon(
                    Icons.close,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                  label: Text(
                    'Passer',
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
            ),

            // Carousel
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                onPageChanged: (page) {
                  setState(() => _currentPage = page);
                },
                itemCount: _slides.length,
                itemBuilder: (context, index) {
                  final slide = _slides[index];
                  return _SlideBuilder(slide: slide, padding: padding);
                },
              ),
            ),

            // Page indicators
            Padding(
              padding: EdgeInsets.symmetric(vertical: padding),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  _slides.length,
                  (index) => Container(
                    width: _currentPage == index ? 28 : 8,
                    height: 8,
                    margin: const EdgeInsets.symmetric(horizontal: 4),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      color: _currentPage == index
                          ? Theme.of(context).colorScheme.primary
                          : Theme.of(context).colorScheme.outline,
                    ),
                  ),
                ),
              ),
            ),

            // Bottom button
            Padding(
              padding: EdgeInsets.all(padding),
              child: PrimaryButton(
                label: _currentPage == _slides.length - 1
                    ? 'Commencer'
                    : 'Suivant',
                onPressed: _nextSlide,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Tutorial slide widget.
class _SlideBuilder extends StatelessWidget {
  const _SlideBuilder({required this.slide, required this.padding});

  final TutorialSlide slide;
  final double padding;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final color = slide.isAccent ? cs.secondary : cs.primary;
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Large icon
        Container(
          width: 120,
          height: 120,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            shape: BoxShape.circle,
          ),
          child: Icon(slide.icon, size: 64, color: color),
        ),
        const SizedBox(height: AppSpacing.xl),

        // Title
        Padding(
          padding: EdgeInsets.symmetric(horizontal: padding),
          child: Text(
            slide.title,
            style: AppTypography.titleLarge,
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: AppSpacing.md),

        // Description
        Padding(
          padding: EdgeInsets.symmetric(horizontal: padding),
          child: Text(
            slide.description,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );
  }
}

/// Represents a single tutorial slide.
class TutorialSlide {
  /// Constructor.
  const TutorialSlide({
    required this.title,
    required this.description,
    required this.icon,
    this.isAccent = false,
  });

  /// Slide title.
  final String title;

  /// Slide description.
  final String description;

  /// Large icon to display.
  final IconData icon;

  /// Whether to use secondary (accent) color instead of primary.
  final bool isAccent;
}
