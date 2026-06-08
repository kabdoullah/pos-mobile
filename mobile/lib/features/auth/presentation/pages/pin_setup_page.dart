import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../providers/auth_providers.dart';
import '../widgets/pin_numpad.dart';
import '../widgets/registration_stepper.dart';

/// PIN setup screen — two-step create + confirm flow with custom numpad.
///
/// Step 0: user enters a new PIN (trivial PINs rejected).
/// Step 1: user confirms the PIN; match triggers [AuthNotifier.setupPin].
class PinSetupPage extends ConsumerStatefulWidget {
  /// Creates a PIN setup page.
  const PinSetupPage({super.key});

  @override
  ConsumerState<PinSetupPage> createState() => _PinSetupPageState();
}

class _PinSetupPageState extends ConsumerState<PinSetupPage> {
  String _pin = '';
  String _firstPin = '';

  /// 0 = create, 1 = confirm.
  int _step = 0;
  String? _error;

  static final _logger = Logger();

  static const _trivialPins = {
    '0123',
    '1234',
    '2345',
    '3456',
    '4567',
    '5678',
    '6789',
    '9876',
    '8765',
    '7654',
    '6543',
    '5432',
    '4321',
  };

  bool _isTrivialPin(String pin) {
    if (pin.isNotEmpty && pin.split('').every((c) => c == pin[0])) return true;
    return _trivialPins.contains(pin);
  }

  void _onDigit(String digit) {
    if (_pin.length >= 4) return;
    setState(() {
      _pin += digit;
      _error = null;
    });
    if (_pin.length == 4) unawaited(_onPinComplete());
  }

  void _onBackspace() {
    if (_pin.isEmpty) return;
    setState(() {
      _pin = _pin.substring(0, _pin.length - 1);
      _error = null;
    });
  }

  Future<void> _onPinComplete() async {
    if (_step == 0) {
      if (_isTrivialPin(_pin)) {
        setState(() {
          _error = 'PIN trop simple (ex : 1234, 0000)';
          _pin = '';
        });
        return;
      }
      setState(() {
        _firstPin = _pin;
        _pin = '';
        _step = 1;
      });
    } else {
      if (_pin != _firstPin) {
        setState(() {
          _error = 'Les PIN ne correspondent pas';
          _pin = '';
        });
        return;
      }
      _logger.i('PIN validation passed, calling setupPin()');
      try {
        await ref.read(authProvider.notifier).setupPin(_firstPin);
        _logger.i('setupPin() completed, router should redirect');
      } catch (_) {
        // Error displayed via authValue.asError
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final authValue = ref.watch(authProvider);
    final systemError = authValue.asError?.error.toString();
    final isLoading = authValue.isLoading;
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
          child: Column(
            children: [
              const SizedBox(height: AppSpacing.md),
              const RegistrationStepper(currentStep: 3),
              const Spacer(),
              // System error banner
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                child: systemError != null
                    ? Container(
                        key: const ValueKey('sys-error'),
                        margin: const EdgeInsets.only(bottom: AppSpacing.md),
                        padding: const EdgeInsets.symmetric(
                          horizontal: AppSpacing.sm,
                          vertical: AppSpacing.xs,
                        ),
                        decoration: BoxDecoration(
                          color: cs.errorContainer,
                          borderRadius: BorderRadius.circular(
                            AppSpacing.radiusSm,
                          ),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.error_outline,
                              color: cs.onErrorContainer,
                              size: 18,
                            ),
                            const SizedBox(width: AppSpacing.xs),
                            Expanded(
                              child: Text(
                                systemError,
                                style: AppTypography.bodySmall.copyWith(
                                  color: cs.onErrorContainer,
                                ),
                              ),
                            ),
                          ],
                        ),
                      )
                    : const SizedBox.shrink(),
              ),
              // ✨ AnimatedSwitcher — transition douce entre les étapes create/confirm
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 300),
                transitionBuilder: (child, animation) => ScaleTransition(
                  scale: animation,
                  child: FadeTransition(opacity: animation, child: child),
                ),
                child: Container(
                  key: ValueKey(_step),
                  width: 72,
                  height: 72,
                  decoration: BoxDecoration(
                    color: cs.primaryContainer,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
                  ),
                  child: Icon(
                    _step == 0
                        ? Icons.add_moderator_rounded
                        : Icons.check_circle_outline_rounded,
                    size: 36,
                    color: cs.onPrimaryContainer,
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              // ✨ AnimatedSwitcher sur le titre — transition visuelle cohérente
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                child: Text(
                  _step == 0 ? 'Créez votre PIN' : 'Confirmez votre PIN',
                  key: ValueKey('title-$_step'),
                  style: AppTypography.titleLarge.copyWith(color: cs.onSurface),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                child: Text(
                  _step == 0
                      ? 'Évitez les codes simples : 0000, 1234…'
                      : 'Entrez à nouveau votre PIN pour confirmer',
                  key: ValueKey('subtitle-$_step'),
                  style: AppTypography.bodyMedium.copyWith(
                    color: cs.onSurfaceVariant,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              // Dot indicators
              PinDots(filledCount: _pin.length),
              // Field error (trivial PIN / mismatch)
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                child: _error != null
                    ? Padding(
                        key: ValueKey(_error),
                        padding: const EdgeInsets.only(top: AppSpacing.sm),
                        child: Semantics(
                          liveRegion: true,
                          child: Text(
                            _error!,
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
              // Custom numpad
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
              const SizedBox(height: AppSpacing.lg),
            ],
          ),
        ),
      ),
    );
  }
}
