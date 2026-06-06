// ============================================================
// AVANT → APRÈS : RegisterPage
// Flutter 3.x+ | Material 3 | Dart 3+ | POS Mobile
// ============================================================
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/auth_providers.dart';
import '../widgets/registration_stepper.dart';

/// User registration page (email + password).
///
/// Validates email, password strength, and phone number format.
/// Creates new account and stores JWT tokens securely.
class RegisterPage extends ConsumerStatefulWidget {
  /// Creates a register page.
  const RegisterPage({super.key});

  @override
  ConsumerState<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  late TextEditingController _emailController;
  late TextEditingController _passwordController;
  late TextEditingController _confirmPasswordController;
  late TextEditingController _phoneController;

  String? _emailError;
  String? _passwordError;
  String? _confirmPasswordError;
  String? _phoneError;

  @override
  void initState() {
    super.initState();
    _emailController = TextEditingController();
    _passwordController = TextEditingController();
    _confirmPasswordController = TextEditingController();
    _phoneController = TextEditingController();
    // Clear any stale auth error from previous login attempt.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(authProvider.notifier).clearError();
    });
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  bool _validateForm() {
    _emailError = null;
    _passwordError = null;
    _confirmPasswordError = null;
    _phoneError = null;

    final email = _emailController.text.trim();
    final password = _passwordController.text;
    final confirmPassword = _confirmPasswordController.text;
    final phone = _phoneController.text.trim();

    bool isValid = true;

    // Email validation.
    if (email.isEmpty) {
      _emailError = 'Email requis';
      isValid = false;
    } else if (!_isValidEmail(email)) {
      _emailError = 'Email invalide';
      isValid = false;
    }

    // Password validation.
    if (password.isEmpty) {
      _passwordError = 'Mot de passe requis';
      isValid = false;
    } else if (password.length < 8) {
      _passwordError = 'Au moins 8 caractères';
      isValid = false;
    }

    // Confirm password validation.
    if (confirmPassword.isEmpty) {
      _confirmPasswordError = 'Confirmation requise';
      isValid = false;
    } else if (password != confirmPassword) {
      _confirmPasswordError = 'Les mots de passe ne correspondent pas';
      isValid = false;
    }

    // Phone validation (basic format for Côte d'Ivoire).
    if (phone.isEmpty) {
      _phoneError = 'Téléphone requis';
      isValid = false;
    } else if (!_isValidPhoneCI(phone)) {
      _phoneError = 'Format invalide (ex: +225 0123456789)';
      isValid = false;
    }

    setState(() {});
    return isValid;
  }

  bool _isValidEmail(String email) {
    return email.contains('@') && email.contains('.');
  }

  bool _isValidPhoneCI(String phone) {
    // Accept: +225XXXXXXXXXX, 225XXXXXXXXXX, or XXXXXXXXXX
    final cleaned = phone.replaceAll(RegExp(r'\D'), '');
    if (cleaned.startsWith('225')) {
      return cleaned.length == 12;
    }
    return cleaned.length == 10;
  }

  Future<void> _register() async {
    if (!_validateForm()) return;

    try {
      final authNotifier = ref.read(authProvider.notifier);
      await authNotifier.register(
        _emailController.text.trim(),
        _passwordController.text,
        _phoneController.text.trim(),
      );
      // Router redirect automatically handles navigation based on new auth state
      // (AuthStateStoreSetupRequired → /store-setup)
    } catch (_) {
      // Error state already handled by authProvider state display above
    }
  }

  @override
  Widget build(BuildContext context) {
    // ✨ Centralize colorScheme access — used throughout build
    final cs = Theme.of(context).colorScheme;
    final authValue = ref.watch(authProvider);
    final isLoading = authValue.isLoading;
    final errorMessage = authValue.asError?.error.toString();

    final spacing = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );

    return Scaffold(
      // ✨ Removed backgroundColor: AppColors.background — theme handles light/dark
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(
                spacing,
                spacing,
                spacing,
                AppSpacing.lg,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const RegistrationStepper(currentStep: 1),
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    'Créer votre compte',
                    // ✨ Explicit onSurface — readable in both light and dark
                    style: AppTypography.titleLarge.copyWith(
                      color: cs.onSurface,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Renseignez vos informations pour ouvrir votre espace marchand.',
                    // ✨ colorScheme.onSurfaceVariant replaces AppColors.textSecondary — dark mode safe
                    style: AppTypography.bodyMedium.copyWith(
                      color: cs.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(spacing, 0, spacing, spacing),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // ✨ AnimatedSwitcher — smooth 200ms entrance/exit, no layout jump
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 200),
                      child: errorMessage != null
                          ? Semantics(
                              // ✨ liveRegion — screen reader announces error immediately
                              liveRegion: true,
                              key: const ValueKey('error-banner'),
                              child: Container(
                                margin: const EdgeInsets.only(
                                  bottom: AppSpacing.lg,
                                ),
                                padding: const EdgeInsets.all(AppSpacing.md),
                                decoration: BoxDecoration(
                                  // ✨ M3 errorContainer — adapts to dark mode
                                  color: cs.errorContainer,
                                  border: Border.all(color: cs.error),
                                  borderRadius: BorderRadius.circular(
                                    AppSpacing.radiusMd, // ✨ token replaces hardcoded 8
                                  ),
                                ),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    // ✨ Icon — don't rely on color alone (WCAG 1.4.1)
                                    Icon(
                                      Icons.error_outline,
                                      color: cs.onErrorContainer,
                                      size: 20,
                                    ),
                                    const SizedBox(width: AppSpacing.sm),
                                    Expanded(
                                      child: Text(
                                        errorMessage,
                                        // ✨ onErrorContainer — proper contrast on error bg
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
                    AppTextField(
                      label: 'Email',
                      hint: 'ab@gmail.com',
                      controller: _emailController,
                      keyboardType: TextInputType.emailAddress,
                      errorText: _emailError,
                      prefixIcon: Icons.email_outlined,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AppTextField(
                      label: 'Mot de passe',
                      hint: 'Au moins 8 caractères',
                      controller: _passwordController,
                      obscureText: true,
                      errorText: _passwordError,
                      prefixIcon: Icons.lock_outlined,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AppTextField(
                      label: 'Confirmer le mot de passe',
                      controller: _confirmPasswordController,
                      obscureText: true,
                      errorText: _confirmPasswordError,
                      prefixIcon: Icons.lock_outlined,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AppTextField(
                      label: 'Téléphone',
                      hint: '+225 0123456789',
                      controller: _phoneController,
                      keyboardType: TextInputType.phone,
                      errorText: _phoneError,
                      prefixIcon: Icons.phone_outlined,
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    PrimaryButton(
                      label: 'Créer mon compte',
                      onPressed: isLoading ? null : _register,
                      isLoading: isLoading,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'Vous avez un compte ? ',
                          // ✨ onSurfaceVariant replaces implicit default — explicit dark mode safe
                          style: AppTypography.bodyMedium.copyWith(
                            color: cs.onSurfaceVariant,
                          ),
                        ),
                        TextButton(
                          onPressed: () => context.go(Routes.emailLogin),
                          child: const Text('Connectez-vous'),
                        ),
                      ],
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
