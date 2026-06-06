// ============================================================
// AVANT → APRÈS : PinSetupPage
// Flutter 3.x+ | Material 3 | Dart 3+ | POS Mobile
// ============================================================
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';
import 'package:pinput/pinput.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/auth_providers.dart';
import '../widgets/registration_stepper.dart';

/// PIN setup screen after store configuration.
///
/// User sets and confirms a 4-digit PIN on a single page.
/// Prevents trivial PINs (0000, 1234, etc.).
class PinSetupPage extends ConsumerStatefulWidget {
  /// Creates a PIN setup page.
  const PinSetupPage({super.key});

  @override
  ConsumerState<PinSetupPage> createState() => _PinSetupPageState();
}

class _PinSetupPageState extends ConsumerState<PinSetupPage> {
  late TextEditingController _pinController;
  late TextEditingController _confirmPinController;

  // ✨ [UX] FocusNodes pour auto-advance PIN → confirm PIN
  late FocusNode _pinFocusNode;
  late FocusNode _confirmPinFocusNode;

  String? _pinError;
  String? _confirmPinError;

  static final _logger = Logger();

  @override
  void initState() {
    super.initState();
    _pinController = TextEditingController();
    _confirmPinController = TextEditingController();
    _pinFocusNode = FocusNode();
    _confirmPinFocusNode = FocusNode();
  }

  @override
  void dispose() {
    _pinController.dispose();
    _confirmPinController.dispose();
    _pinFocusNode.dispose();
    _confirmPinFocusNode.dispose();
    super.dispose();
  }

  bool _isTrivialPin(String pin) {
    final first = pin.isNotEmpty ? pin[0] : '';
    if (first.isNotEmpty && pin.split('').every((c) => c == first)) {
      return true;
    }
    return pin == '0123' ||
        pin == '1234' ||
        pin == '2345' ||
        pin == '3456' ||
        pin == '4567' ||
        pin == '5678' ||
        pin == '6789' ||
        pin == '9876' ||
        pin == '8765' ||
        pin == '7654' ||
        pin == '6543' ||
        pin == '5432' ||
        pin == '4321';
  }

  Future<void> _submit() async {
    final pin = _pinController.text;
    final confirmPin = _confirmPinController.text;

    _pinError = null;
    _confirmPinError = null;

    if (pin.isEmpty) {
      _pinError = 'PIN requis';
    } else if (pin.length != 4) {
      _pinError = '4 chiffres requis';
    } else if (_isTrivialPin(pin)) {
      _pinError = 'PIN trop simple (ex: 1234, 0000)';
    }

    if (_pinError == null) {
      if (confirmPin.isEmpty) {
        _confirmPinError = 'Confirmation requise';
      } else if (pin != confirmPin) {
        _confirmPinError = 'Les PIN ne correspondent pas';
      }
    }

    if (_pinError != null || _confirmPinError != null) {
      setState(() {});
      return;
    }

    _logger.i('PIN validation passed, calling setupPin()');
    try {
      await ref.read(authProvider.notifier).setupPin(pin);
      _logger.i('setupPin() completed, router should redirect');
    } catch (_) {
      // System error displayed via authValue.asError below.
    }
  }

  /// Builds a [PinTheme] with colorScheme-aware text and border.
  PinTheme _buildPinTheme(
    Color borderColor, {
    required Color textColor,
    required Color fillColor,
  }) =>
      PinTheme(
        width: 60,
        height: 60,
        // ✨ Explicit textColor — dark mode safe, no ambient color leak
        textStyle: AppTypography.amountDisplay.copyWith(color: textColor),
        decoration: BoxDecoration(
          // ✨ fillColor distinguishes cells from scaffold background
          color: fillColor,
          borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
          border: Border.all(color: borderColor, width: 2),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final authValue = ref.watch(authProvider);
    final systemError = authValue.asError?.error.toString();
    final isLoading = authValue.isLoading;

    final padding = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );

    // ✨ Shared PinTheme args — avoids repeating cs references
    final defaultTheme = _buildPinTheme(
      cs.outline,
      textColor: cs.onSurface,
      fillColor: cs.surfaceContainerHighest,
    );
    final focusedTheme = _buildPinTheme(
      cs.primary,
      textColor: cs.onSurface,
      fillColor: cs.surfaceContainerHighest,
    );
    final errorTheme = _buildPinTheme(
      cs.error,
      textColor: cs.onSurface,
      fillColor: cs.errorContainer,
    );

    return Scaffold(
      // ✨ Removed backgroundColor: AppColors.background — theme handles light/dark
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(
                padding,
                padding,
                padding,
                AppSpacing.lg,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const RegistrationStepper(currentStep: 3),
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    'Sécurité du compte',
                    // ✨ Explicit onSurface — readable in light and dark
                    style: AppTypography.titleLarge.copyWith(
                      color: cs.onSurface,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    "Protégez l'accès à votre point de vente. Ce code PIN sera requis pour chaque transaction et ouverture de caisse.",
                    // ✨ onSurfaceVariant replaces AppColors.textSecondary — dark mode safe
                    style: AppTypography.bodyMedium.copyWith(
                      color: cs.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(padding, 0, padding, padding),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ✨ systemError as top banner — distinct from field-level errors
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 200),
                      child: systemError != null
                          ? Semantics(
                              // ✨ liveRegion — screen reader announces system error
                              liveRegion: true,
                              key: const ValueKey('system-error-banner'),
                              child: Container(
                                margin: const EdgeInsets.only(
                                  bottom: AppSpacing.lg,
                                ),
                                padding: const EdgeInsets.all(AppSpacing.md),
                                decoration: BoxDecoration(
                                  color: cs.errorContainer,
                                  border: Border.all(color: cs.error),
                                  borderRadius: BorderRadius.circular(
                                    AppSpacing.radiusMd,
                                  ),
                                ),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Icon(
                                      Icons.error_outline,
                                      color: cs.onErrorContainer,
                                      size: 20,
                                    ),
                                    const SizedBox(width: AppSpacing.sm),
                                    Expanded(
                                      child: Text(
                                        systemError,
                                        style: AppTypography.bodyMedium.copyWith(
                                          color: cs.onErrorContainer,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            )
                          : const SizedBox.shrink(),
                    ),
                    Text(
                      'Créez votre PIN',
                      // ✨ Explicit onSurface — consistent label hierarchy
                      style: AppTypography.labelMedium.copyWith(
                        color: cs.onSurface,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      'Évitez les codes simples : 0000, 1234…',
                      // ✨ onSurfaceVariant — secondary hint, visually subordinate
                      style: AppTypography.captionText.copyWith(
                        color: cs.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Center(
                      child: Pinput(
                        controller: _pinController,
                        focusNode: _pinFocusNode,
                        length: 4,
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        obscureText: true,
                        // ✨ [UX] autofocus — ouvre le clavier immédiatement à l'arrivée sur l'écran
                        autofocus: true,
                        defaultPinTheme: defaultTheme,
                        focusedPinTheme: focusedTheme,
                        errorPinTheme: errorTheme,
                        onChanged: (_) => setState(() => _pinError = null),
                        // ✨ [UX] auto-advance — focus passe au confirm PIN après le 4ᵉ chiffre
                        onCompleted: (_) =>
                            _confirmPinFocusNode.requestFocus(),
                      ),
                    ),
                    // ✨ Inline field error with icon — WCAG 1.4.1 (not color alone)
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 150),
                      child: _pinError != null
                          ? Semantics(
                              liveRegion: true,
                              key: const ValueKey('pin-error'),
                              child: Padding(
                                padding: const EdgeInsets.only(top: AppSpacing.sm),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Icon(
                                      Icons.info_outline,
                                      size: 16,
                                      color: cs.error,
                                    ),
                                    const SizedBox(width: AppSpacing.xs),
                                    Text(
                                      _pinError!,
                                      // ✨ Applied cs.error — previously inherited onSurface
                                      style: AppTypography.errorText.copyWith(
                                        color: cs.error,
                                      ),
                                      textAlign: TextAlign.center,
                                    ),
                                  ],
                                ),
                              ),
                            )
                          : const SizedBox.shrink(),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Text(
                      'Confirmez votre PIN',
                      style: AppTypography.labelMedium.copyWith(
                        color: cs.onSurface,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Center(
                      child: Pinput(
                        controller: _confirmPinController,
                        focusNode: _confirmPinFocusNode,
                        length: 4,
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        obscureText: true,
                        defaultPinTheme: defaultTheme,
                        focusedPinTheme: focusedTheme,
                        errorPinTheme: errorTheme,
                        onChanged: (_) =>
                            setState(() => _confirmPinError = null),
                        // ✨ [UX] soumet automatiquement après le 4ᵉ chiffre de confirmation
                        onCompleted: (_) => _submit(),
                      ),
                    ),
                    // ✨ Confirm error distinct from systemError (now a top banner)
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 150),
                      child: _confirmPinError != null
                          ? Semantics(
                              liveRegion: true,
                              key: const ValueKey('confirm-pin-error'),
                              child: Padding(
                                padding: const EdgeInsets.only(top: AppSpacing.sm),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Icon(
                                      Icons.info_outline,
                                      size: 16,
                                      color: cs.error,
                                    ),
                                    const SizedBox(width: AppSpacing.xs),
                                    Text(
                                      _confirmPinError!,
                                      style: AppTypography.errorText.copyWith(
                                        color: cs.error,
                                      ),
                                      textAlign: TextAlign.center,
                                    ),
                                  ],
                                ),
                              ),
                            )
                          : const SizedBox.shrink(),
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    PrimaryButton(
                      label: 'Confirmer',
                      onPressed: isLoading ? null : _submit,
                      isLoading: isLoading,
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
