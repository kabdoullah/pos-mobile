import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:logger/logger.dart';

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
  static final _logger = Logger();
  late DateTime _splashStartTime;
  bool _hasNavigated = false;

  @override
  void initState() {
    super.initState();
    _logger.i('[Splash] SplashPage mounted');
    _splashStartTime = DateTime.now();
  }

  void _navigateBasedOnAuthState(AuthState authState) {
    switch (authState) {
      case AuthStateUnauthenticated():
        _logger.i('[Splash] Unauthenticated, going to email login');
        context.go(Routes.emailLogin);
      case AuthStatePinRequired():
        _logger.i('[Splash] PIN required, going to pin login');
        context.go(Routes.pinLogin);
      case AuthStatePinSetupRequired():
        _logger.i('[Splash] PIN setup required, going to pin setup');
        context.go(Routes.pinSetup);
      case AuthStateAuthenticated():
        _logger.i('[Splash] User authenticated, checking sync');
        final isOnline = ref.read(isOnlineProvider).value ?? false;
        if (isOnline) {
          _logger.i('[Splash] Online, syncing');
          unawaited(ref.read(syncOrchestratorProvider.notifier).syncNow());
        }
        _logger.i('[Splash] Going to home');
        context.go(Routes.home);
      case AuthStateError():
        _logger.e('[Splash] Auth error, staying on splash');
      case AuthStateLoading():
        // Should not reach here due to early return
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch auth state and navigate when it changes (and minimum splash time passed).
    final authState = ref.watch(authProvider);
    if (!_hasNavigated && authState is! AuthStateLoading) {
      _checkAndNavigate(authState);
    }

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

  void _checkAndNavigate(AuthState authState) {
    _logger.i('[Splash] Auth state changed: ${authState.runtimeType}');

    // Ensure minimum splash display time (1 second for visual polish).
    final elapsedMs = DateTime.now()
        .difference(_splashStartTime)
        .inMilliseconds;
    final remainingMs = 1000 - elapsedMs;

    if (remainingMs > 0) {
      Future<void>.delayed(Duration(milliseconds: remainingMs), () {
        if (mounted && !_hasNavigated) {
          _hasNavigated = true;
          _navigateBasedOnAuthState(authState);
        }
      });
    } else {
      _hasNavigated = true;
      _navigateBasedOnAuthState(authState);
    }
  }
}
