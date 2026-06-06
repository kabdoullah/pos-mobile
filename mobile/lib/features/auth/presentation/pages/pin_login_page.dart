import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:pinput/pinput.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../providers/auth_providers.dart';
import '../providers/store_provider.dart';

/// Daily PIN login screen.
///
/// Quick access with just the PIN. Shows store name and welcome message.
/// Handles PIN attempt limits with 5-minute lockout (4 max attempts).
class PinLoginPage extends ConsumerStatefulWidget {
  /// Creates a PIN login page.
  const PinLoginPage({super.key});

  @override
  ConsumerState<PinLoginPage> createState() => _PinLoginPageState();
}

class _PinLoginPageState extends ConsumerState<PinLoginPage>
    with TickerProviderStateMixin {
  late TextEditingController _pinController;
  // ✨ entrée en scène échelonnée + shake horizontal sur erreur
  late AnimationController _entranceController;
  late AnimationController _shakeController;
  late Animation<Offset> _shakeAnimation;

  String? _error;

  @override
  void initState() {
    super.initState();
    _pinController = TextEditingController();

    _entranceController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    unawaited(_entranceController.forward());

    _shakeController = AnimationController(
      duration: const Duration(milliseconds: 420),
      vsync: this,
    );
    // ✨ TweenSequence → shake gauche-droite-centre naturel
    _shakeAnimation = TweenSequence<Offset>([
      TweenSequenceItem(
        tween: Tween(begin: Offset.zero, end: const Offset(0.04, 0)),
        weight: 1,
      ),
      TweenSequenceItem(
        tween: Tween(begin: const Offset(0.04, 0), end: const Offset(-0.04, 0)),
        weight: 2,
      ),
      TweenSequenceItem(
        tween: Tween(begin: const Offset(-0.04, 0), end: const Offset(0.02, 0)),
        weight: 1,
      ),
      TweenSequenceItem(
        tween: Tween(begin: const Offset(0.02, 0), end: Offset.zero),
        weight: 1,
      ),
    ]).animate(CurvedAnimation(parent: _shakeController, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _pinController.dispose();
    _entranceController.dispose();
    _shakeController.dispose();
    super.dispose();
  }

  Future<void> _onForgotPin() async {
    // Forgot PIN: clear local PIN + tokens so a fresh PIN setup is required
    // after the user re-authenticates with email + password. logout() moves
    // auth state to Unauthenticated, which lets the router reach email login.
    await ref.read(authProvider.notifier).logout();
    if (mounted) context.go(Routes.emailLogin);
  }

  PinTheme _buildPinTheme(Color borderColor) => PinTheme(
    width: 70,
    height: 70,
    textStyle: AppTypography.amountDisplay,
    decoration: BoxDecoration(
      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      border: Border.all(color: borderColor, width: 2),
    ),
  );

  Future<void> _verifyPin() async {
    final pin = _pinController.text;
    if (pin.length != 4) {
      setState(() => _error = '4 chiffres requis');
      // ✨ shake immédiat sur validation locale
      unawaited(_shakeController.forward(from: 0));
      return;
    }

    try {
      final authNotifier = ref.read(authProvider.notifier);
      await authNotifier.verifyPin(pin);
      // Router handles redirect automatically when state becomes AuthAuthenticated
    } catch (_) {
      // Error state already displayed via systemError (from authValue.asError)
    }
  }

  /// Construit une animation de fondu échelonnée pour l'entrée en scène.
  Animation<double> _fade(double start) => Tween<double>(
    begin: 0,
    end: 1,
  ).animate(
    CurvedAnimation(
      parent: _entranceController,
      curve: Interval(start, (start + 0.45).clamp(0.0, 1.0), curve: Curves.easeOut),
    ),
  );

  static String _timeGreeting() {
    final hour = DateTime.now().hour;
    if (hour < 12) return 'Bon matin,';
    if (hour < 18) return 'Bon après-midi,';
    return 'Bonsoir,';
  }

  /// Construit une animation de glissement vers le haut pour l'entrée en scène.
  Animation<Offset> _slide(double start) => Tween<Offset>(
    begin: const Offset(0, 0.3),
    end: Offset.zero,
  ).animate(
    CurvedAnimation(
      parent: _entranceController,
      curve: Interval(start, (start + 0.45).clamp(0.0, 1.0), curve: Curves.easeOut),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final authValue = ref.watch(authProvider);
    final systemError = authValue.asError?.error.toString();
    final cs = Theme.of(context).colorScheme;
    final storeName =
        ref.watch(storeConfigProvider).whenOrNull(data: (s) => s?.name) ??
        'Ma boutique';

    // ✨ réagit aux transitions d'état auth — shake + vide le champ sur erreur
    ref.listen(authProvider, (_, next) {
      if (next.hasError) {
        _pinController.clear();
        unawaited(_shakeController.forward(from: 0));
      }
    });

    final spacing = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );

    return Scaffold(
      // ✨ backgroundColor géré par le theme M3 — AppColors.background supprimé
      resizeToAvoidBottomInset: false,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              padding: EdgeInsets.symmetric(horizontal: spacing),
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ✨ icône — entre en premier (0.0)
                    FadeTransition(
                      opacity: _fade(0.0),
                      child: SlideTransition(
                        position: _slide(0.0),
                        child: Icon(
                          Icons.storefront_rounded,
                          size: 48,
                          color: cs.primary, // ✨ cs.primary — AppColors.primary supprimé
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    // ✨ titre + sous-titre — décalage +100ms
                    FadeTransition(
                      opacity: _fade(0.1),
                      child: SlideTransition(
                        position: _slide(0.1),
                        // ✨ salutation dynamique : heure + nom boutique + accroche POS
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _timeGreeting(),
                              style: AppTypography.bodyMedium.copyWith(
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            Text(storeName, style: AppTypography.titleLarge),
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              'Prêt à encaisser ?',
                              style: AppTypography.bodySmall.copyWith(
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xxl),
                    // ✨ Pinput — décalage +250ms, shake horizontal sur erreur
                    FadeTransition(
                      opacity: _fade(0.25),
                      child: SlideTransition(
                        position: _slide(0.25),
                        child: Center(
                          child: SlideTransition(
                            position: _shakeAnimation,
                            child: authValue.isLoading
                                // ✨ spinner pendant la vérification du PIN
                                ? const SizedBox(
                                    height: 70,
                                    child: Center(
                                      child: CircularProgressIndicator(),
                                    ),
                                  )
                                : Pinput(
                                    controller: _pinController,
                                    length: 4,
                                    mainAxisAlignment:
                                        MainAxisAlignment.spaceEvenly,
                                    obscureText: true,
                                    defaultPinTheme: _buildPinTheme(cs.outline),
                                    focusedPinTheme: _buildPinTheme(cs.primary),
                                    errorPinTheme: _buildPinTheme(cs.error),
                                    onCompleted: (_) => _verifyPin(),
                                    onChanged: (_) =>
                                        setState(() => _error = null),
                                  ),
                          ),
                        ),
                      ),
                    ),
                    // ✨ AnimatedSwitcher — fade in/out du message d'erreur
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 250),
                      child: (_error != null || systemError != null)
                          ? Padding(
                              // key = rerend le widget si le message change
                              key: ValueKey(_error ?? systemError),
                              padding: const EdgeInsets.only(
                                top: AppSpacing.md,
                              ),
                              child: Center(
                                child: Text(
                                  _error ?? systemError!,
                                  style: AppTypography.errorText.copyWith(color: cs.error), // ✨ WCAG 1.4.1 — couleur appliquée au call site
                                  textAlign: TextAlign.center,
                                ),
                              ),
                            )
                          : const SizedBox.shrink(),
                    ),
                    const SizedBox(height: AppSpacing.xxl),
                    // ✨ bouton — entre en dernier (0.5)
                    FadeTransition(
                      opacity: _fade(0.5),
                      child: Center(
                        child: TextButton(
                          onPressed: _onForgotPin,
                          child: const Text('J\'ai oublié mon PIN'),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
