import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/sync/sync_orchestrator.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/providers/connectivity_provider.dart';
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
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkAuthStatus();
    });
  }

  void _checkAuthStatus() {
    // Give the splash a minimum display time for visual polish.
    unawaited(
      Future<void>.delayed(const Duration(seconds: 1)).then((_) {
        if (!mounted) return;

        final authState = ref.read(authProvider);

        // Route based on auth state.
        // Let GoRouter redirect logic handle auth state routing.
        if (authState is! AuthStateLoading) {
          // Trigger background sync if authenticated and online
          if (authState is AuthStateAuthenticated) {
            final isOnline = ref.read(isOnlineProvider).value ?? false;
            if (isOnline) {
              unawaited(ref.read(syncOrchestratorProvider.notifier).syncNow());
            }
          }

          if (mounted) {
            context.go(Routes.home);
          }
        }
      }),
    );
  }

  @override
  Widget build(BuildContext context) {
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
