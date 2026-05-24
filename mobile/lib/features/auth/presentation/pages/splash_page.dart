import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../providers/auth_providers.dart';

/// Splash/loading screen.
///
/// Displays app logo and determines where to redirect based on auth state.
/// Initializes auth state by checking for existing session.
class SplashPage extends ConsumerStatefulWidget {
  /// Creates a splash page.
  const SplashPage({super.key});

  @override
  ConsumerState<SplashPage> createState() => _SplashPageState();
}

class _SplashPageState extends ConsumerState<SplashPage> {
  static final _logger = Logger();

  @override
  void initState() {
    super.initState();
    _logger.i('[Splash] SplashPage mounted');
    _delayMinimumSplashTime();
  }

  void _delayMinimumSplashTime() {
    // Ensure minimum splash display time (1 second for visual polish) before redirect.
    Future<void>.delayed(const Duration(seconds: 1), () {
      if (mounted) {
        _logger.i(
          '[Splash] Minimum splash time elapsed, triggering router refresh',
        );
        // Trigger router redirect mechanism to navigate based on auth state.
        ref.read(appRouterProvider).refresh();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    // Watch auth state to trigger router refresh when it changes.
    ref.watch(authProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.storefront_rounded,
              size: 64,
              color: AppColors.primary,
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              'POS Mobile',
              style: AppTypography.titleLarge.copyWith(
                color: AppColors.primary,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            const Text('Pour votre boutique', style: AppTypography.bodyMedium),
          ],
        ),
      ),
    );
  }
}
