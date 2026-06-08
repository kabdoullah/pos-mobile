import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../providers/auth_providers.dart';
import '../../providers/store_provider.dart';
import '../widgets/pin_numpad.dart';

/// Daily PIN login screen with custom numpad.
///
/// Replaces system keyboard with a 3×4 numpad and dot indicators.
/// Handles 5-attempt lockout; shake animation on wrong PIN.
class PinLoginPage extends ConsumerStatefulWidget {
  /// Creates a PIN login page.
  const PinLoginPage({super.key});

  @override
  ConsumerState<PinLoginPage> createState() => _PinLoginPageState();
}

class _PinLoginPageState extends ConsumerState<PinLoginPage>
    with SingleTickerProviderStateMixin {
  String _pin = '';
  late AnimationController _shakeController;
  late Animation<Offset> _shakeAnimation;

  @override
  void initState() {
    super.initState();
    _shakeController = AnimationController(
      duration: const Duration(milliseconds: 420),
      vsync: this,
    );
    _shakeAnimation =
        TweenSequence<Offset>([
          TweenSequenceItem(
            tween: Tween(begin: Offset.zero, end: const Offset(0.04, 0)),
            weight: 1,
          ),
          TweenSequenceItem(
            tween: Tween(
              begin: const Offset(0.04, 0),
              end: const Offset(-0.04, 0),
            ),
            weight: 2,
          ),
          TweenSequenceItem(
            tween: Tween(
              begin: const Offset(-0.04, 0),
              end: const Offset(0.02, 0),
            ),
            weight: 1,
          ),
          TweenSequenceItem(
            tween: Tween(begin: const Offset(0.02, 0), end: Offset.zero),
            weight: 1,
          ),
        ]).animate(
          CurvedAnimation(parent: _shakeController, curve: Curves.easeInOut),
        );
  }

  @override
  void dispose() {
    _shakeController.dispose();
    super.dispose();
  }

  void _onDigit(String digit) {
    if (_pin.length >= 4) return;
    setState(() => _pin += digit);
    if (_pin.length == 4) unawaited(_verifyPin());
  }

  void _onBackspace() {
    if (_pin.isEmpty) return;
    setState(() => _pin = _pin.substring(0, _pin.length - 1));
  }

  Future<void> _verifyPin() async {
    try {
      await ref.read(authProvider.notifier).verifyPin(_pin);
      // Router redirects automatically on AuthAuthenticated state
    } catch (_) {
      // Error displayed via authValue.asError
    }
  }

  Future<void> _onForgotPin() async {
    await ref.read(authProvider.notifier).logout();
    if (mounted) context.go(Routes.emailLogin);
  }

  static String _timeGreeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Bonjour,';
    if (hour < 18) return 'Bon après-midi,';
    return 'Bonsoir,';
  }

  @override
  Widget build(BuildContext context) {
    final authValue = ref.watch(authProvider);
    final systemError = authValue.asError?.error.toString();
    final isLoading = authValue.isLoading;
    final cs = Theme.of(context).colorScheme;
    final storeName =
        ref.watch(storeConfigProvider).whenOrNull(data: (s) => s?.name) ??
        'Ma boutique';

    ref.listen(authProvider, (_, next) {
      if (next.hasError) {
        setState(() => _pin = '');
        unawaited(_shakeController.forward(from: 0));
      }
    });

    return Scaffold(
      resizeToAvoidBottomInset: false,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
          child: Column(
            children: [
              const Spacer(),
              // Lock icon in branded container
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: cs.primaryContainer,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
                ),
                child: Icon(
                  Icons.lock_rounded,
                  size: 36,
                  color: cs.onPrimaryContainer,
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              Text(
                '${_timeGreeting()} $storeName',
                style: AppTypography.bodyMedium.copyWith(
                  color: cs.onSurfaceVariant,
                ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Entrez votre PIN',
                style: AppTypography.titleLarge.copyWith(color: cs.onSurface),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.xl),
              // Dot indicators — shake on wrong PIN
              SlideTransition(
                position: _shakeAnimation,
                child: PinDots(filledCount: _pin.length),
              ),
              // Error slot — fixed height to avoid layout jump
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                child: systemError != null
                    ? Padding(
                        key: ValueKey(systemError),
                        padding: const EdgeInsets.only(top: AppSpacing.sm),
                        child: Semantics(
                          liveRegion: true,
                          child: Text(
                            systemError,
                            style: AppTypography.errorText.copyWith(
                              color: cs.error,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ),
                      )
                    : const SizedBox(height: AppSpacing.md + AppSpacing.sm),
              ),
              const Spacer(),
              // Custom numpad — no system keyboard
              if (isLoading)
                const SizedBox(
                  height: 290,
                  child: Center(child: CircularProgressIndicator()),
                )
              else
                PinNumpad(
                  onDigit: _onDigit,
                  onBackspace: _onBackspace,
                  enabled: !isLoading,
                ),
              const SizedBox(height: AppSpacing.sm),
              TextButton(
                onPressed: _onForgotPin,
                child: const Text("J'ai oublié mon PIN"),
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
          ),
        ),
      ),
    );
  }
}
