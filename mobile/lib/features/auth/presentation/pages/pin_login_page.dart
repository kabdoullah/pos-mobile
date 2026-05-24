import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:pinput/pinput.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../providers/auth_providers.dart';

/// Daily PIN login screen.
///
/// Quick access with just the PIN. Shows store name and welcome message.
/// Handles PIN attempt limits with 5-minute lockout.
class PinLoginPage extends ConsumerStatefulWidget {
  /// Creates a PIN login page.
  const PinLoginPage({super.key});

  @override
  ConsumerState<PinLoginPage> createState() => _PinLoginPageState();
}

class _PinLoginPageState extends ConsumerState<PinLoginPage> {
  late TextEditingController _pinController;

  String? _error;

  @override
  void initState() {
    super.initState();
    _pinController = TextEditingController();
  }

  @override
  void dispose() {
    _pinController.dispose();
    super.dispose();
  }

  Future<void> _verifyPin() async {
    final pin = _pinController.text;
    if (pin.length != 4) {
      setState(() {
        _error = '4 chiffres requis';
      });
      return;
    }

    try {
      final authNotifier = ref.read(authProvider.notifier);
      await authNotifier.verifyPin(pin);
      // Router handles redirect automatically when state becomes AuthAuthenticated
    } catch (_) {
      // Error state already displayed via systemError (from authValue.asError)
      // No additional error handling needed here
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch auth to display system errors (lockout, network, etc.)
    // Local _error shows PIN validation errors before submit (e.g., "4 chiffres requis")
    final authValue = ref.watch(authProvider);
    final systemError = authValue.asError?.error.toString();

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.all(
            responsiveValue(
              context,
              small: AppSpacing.md,
              medium: AppSpacing.lg,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(height: context.screenHeight * 0.1),
              const Icon(
                Icons.storefront_rounded,
                size: 48,
                color: AppColors.primary,
              ),
              const SizedBox(height: AppSpacing.md),
              const Text('Bonjour !', style: AppTypography.titleLarge),
              const SizedBox(height: AppSpacing.xs),
              const Text(
                'Votre PIN pour commencer',
                style: AppTypography.bodyMedium,
              ),
              SizedBox(height: context.screenHeight * 0.08),
              Center(
                child: Pinput(
                  controller: _pinController,
                  length: 4,
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  obscureText: true,
                  defaultPinTheme: PinTheme(
                    width: 70,
                    height: 70,
                    textStyle: AppTypography.amountDisplay,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                      border: Border.all(color: AppColors.border, width: 2),
                    ),
                  ),
                  focusedPinTheme: PinTheme(
                    width: 70,
                    height: 70,
                    textStyle: AppTypography.amountDisplay,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                      border: Border.all(color: AppColors.primary, width: 2),
                    ),
                  ),
                  errorPinTheme: PinTheme(
                    width: 70,
                    height: 70,
                    textStyle: AppTypography.amountDisplay,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                      border: Border.all(color: AppColors.error, width: 2),
                    ),
                  ),
                  onCompleted: (_) => _verifyPin(),
                  onChanged: (_) => setState(() => _error = null),
                ),
              ),
              // Show either local validation error or system error (lockout, network, etc.)
              if (_error != null || systemError != null) ...[
                const SizedBox(height: AppSpacing.md),
                Center(
                  child: Text(
                    _error ?? systemError!,
                    style: AppTypography.errorText,
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
              SizedBox(height: context.screenHeight * 0.12),
              Center(
                child: GestureDetector(
                  onTap: () => context.go(Routes.emailLogin),
                  child: Text(
                    'J\'ai oublié mon PIN',
                    style: AppTypography.bodyMedium.copyWith(
                      color: AppColors.primary,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
