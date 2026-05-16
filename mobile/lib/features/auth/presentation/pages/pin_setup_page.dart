import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pinput/pinput.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/auth_providers.dart';

/// PIN setup screen after first login.
///
/// User sets a 4-digit PIN for daily login. Prevents trivial PINs.
/// Requires confirmation to ensure user didn't mistype.
class PinSetupPage extends ConsumerStatefulWidget {
  /// Creates a PIN setup page.
  const PinSetupPage({super.key});

  @override
  ConsumerState<PinSetupPage> createState() => _PinSetupPageState();
}

class _PinSetupPageState extends ConsumerState<PinSetupPage> {
  late TextEditingController _pinController;
  late TextEditingController _confirmPinController;

  String? _pinError;
  String? _confirmPinError;

  late PageController _pageController;

  @override
  void initState() {
    super.initState();
    _pinController = TextEditingController();
    _confirmPinController = TextEditingController();
    _pageController = PageController();
  }

  @override
  void dispose() {
    _pinController.dispose();
    _confirmPinController.dispose();
    _pageController.dispose();
    super.dispose();
  }

  bool _isTrivialPin(String pin) {
    // Reject: 0000, 1111, 2222, ..., 9999
    final first = pin.isNotEmpty ? pin[0] : '';
    if (first.isNotEmpty && pin.split('').every((c) => c == first)) {
      return true;
    }

    // Reject: 1234, 0123, etc.
    if (pin == '0123' ||
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
        pin == '4321') {
      return true;
    }

    return false;
  }

  void _nextPage() {
    final pin = _pinController.text;

    _pinError = null;
    if (pin.isEmpty) {
      _pinError = 'PIN requis';
    } else if (pin.length != 4) {
      _pinError = '4 chiffres requis';
    } else if (_isTrivialPin(pin)) {
      _pinError = 'PIN trop simple (ex: 1234, 0000)';
    }

    if (_pinError == null) {
      unawaited(
        _pageController.nextPage(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
        ),
      );
    } else {
      setState(() {});
    }
  }

  Future<void> _confirmPin() async {
    final pin = _pinController.text;
    final confirmPin = _confirmPinController.text;

    _confirmPinError = null;
    if (confirmPin.isEmpty) {
      _confirmPinError = 'Confirmation requise';
    } else if (pin != confirmPin) {
      _confirmPinError = 'Les PIN ne correspondent pas';
    }

    if (_confirmPinError == null) {
      try {
        final authNotifier = ref.read(authProvider.notifier);
        await authNotifier.setupPin(pin);
        // Router redirect automatically handles navigation based on new auth state
        // (AuthStateAuthenticated → /home, etc.)
      } catch (e) {
        if (mounted) {
          setState(() {
            _confirmPinError = 'Erreur: ${e.toString()}';
          });
        }
      }
    } else {
      setState(() {});
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
      appBar: AppBar(title: const Text('Configurez votre PIN'), elevation: 0),
      body: PageView(
        controller: _pageController,
        physics: const NeverScrollableScrollPhysics(),
        children: [
          // Page 1: Create PIN
          SingleChildScrollView(
            padding: EdgeInsets.all(padding),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Créer un PIN', style: AppTypography.titleLarge),
                const SizedBox(height: AppSpacing.xs),
                const Text(
                  'Votre accès quotidien à l\'app',
                  style: AppTypography.bodyMedium,
                ),
                const SizedBox(height: AppSpacing.lg),
                const Text('4 chiffres', style: AppTypography.labelMedium),
                const SizedBox(height: AppSpacing.md),
                Center(
                  child: Pinput(
                    controller: _pinController,
                    length: 4,
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    obscureText: true,
                    defaultPinTheme: PinTheme(
                      width: 60,
                      height: 60,
                      textStyle: AppTypography.amountDisplay,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
                        border: Border.all(color: AppColors.border, width: 2),
                      ),
                    ),
                    focusedPinTheme: PinTheme(
                      width: 60,
                      height: 60,
                      textStyle: AppTypography.amountDisplay,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
                        border: Border.all(color: AppColors.primary, width: 2),
                      ),
                    ),
                    errorPinTheme: PinTheme(
                      width: 60,
                      height: 60,
                      textStyle: AppTypography.amountDisplay,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
                        border: Border.all(color: AppColors.error, width: 2),
                      ),
                    ),
                    onChanged: (_) => setState(() => _pinError = null),
                  ),
                ),
                if (_pinError != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  Center(
                    child: Text(
                      _pinError!,
                      style: AppTypography.errorText,
                      textAlign: TextAlign.center,
                    ),
                  ),
                ],
                const SizedBox(height: AppSpacing.lg),
                const Text(
                  'Évitez les PIN simples comme 0000, 1234',
                  style: AppTypography.captionText,
                ),
                const SizedBox(height: AppSpacing.xl),
                PrimaryButton(label: 'Suivant', onPressed: _nextPage),
              ],
            ),
          ),

          // Page 2: Confirm PIN
          SingleChildScrollView(
            padding: EdgeInsets.all(padding),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Confirmer le PIN', style: AppTypography.titleLarge),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Retapez ${_pinController.text} pour confirmer',
                  style: AppTypography.bodyMedium.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: AppSpacing.lg),
                Center(
                  child: Pinput(
                    controller: _confirmPinController,
                    length: 4,
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    obscureText: true,
                    defaultPinTheme: PinTheme(
                      width: 60,
                      height: 60,
                      textStyle: AppTypography.amountDisplay,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
                        border: Border.all(color: AppColors.border, width: 2),
                      ),
                    ),
                    focusedPinTheme: PinTheme(
                      width: 60,
                      height: 60,
                      textStyle: AppTypography.amountDisplay,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
                        border: Border.all(color: AppColors.primary, width: 2),
                      ),
                    ),
                    errorPinTheme: PinTheme(
                      width: 60,
                      height: 60,
                      textStyle: AppTypography.amountDisplay,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
                        border: Border.all(color: AppColors.error, width: 2),
                      ),
                    ),
                    onChanged: (_) => setState(() => _confirmPinError = null),
                  ),
                ),
                if (_confirmPinError != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  Center(
                    child: Text(
                      _confirmPinError!,
                      style: AppTypography.errorText,
                      textAlign: TextAlign.center,
                    ),
                  ),
                ],
                const SizedBox(height: AppSpacing.xl),
                PrimaryButton(label: 'Confirmer', onPressed: _confirmPin),
                const SizedBox(height: AppSpacing.md),
                Center(
                  child: GestureDetector(
                    onTap: () {
                      _pinController.clear();
                      _confirmPinController.clear();
                      unawaited(
                        _pageController.previousPage(
                          duration: const Duration(milliseconds: 300),
                          curve: Curves.easeInOut,
                        ),
                      );
                    },
                    child: Text(
                      'Recommencer',
                      style: AppTypography.labelMedium.copyWith(
                        color: AppColors.textSecondary,
                        decoration: TextDecoration.underline,
                      ),
                    ),
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
