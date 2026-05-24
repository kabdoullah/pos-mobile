import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/auth_providers.dart';

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

  late bool _obscurePassword;
  late bool _obscureConfirmPassword;

  @override
  void initState() {
    super.initState();
    _emailController = TextEditingController();
    _passwordController = TextEditingController();
    _confirmPasswordController = TextEditingController();
    _phoneController = TextEditingController();
    _obscurePassword = true;
    _obscureConfirmPassword = true;
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
      // No additional error handling needed here
    }
  }

  @override
  Widget build(BuildContext context) {
    final authValue = ref.watch(authProvider);
    final isLoading = authValue.isLoading;
    final errorMessage = authValue.asError?.error.toString();
    // Router handles redirect automatically when state becomes AuthStoreSetupRequired

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SingleChildScrollView(
        padding: EdgeInsets.all(
          responsiveValue(context, small: AppSpacing.md, medium: AppSpacing.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Bienvenue !', style: AppTypography.titleLarge),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Créons votre compte POS Mobile',
              style: AppTypography.bodyMedium.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            if (errorMessage != null) ...[
              Container(
                padding: const EdgeInsets.all(AppSpacing.md),
                decoration: BoxDecoration(
                  color: AppColors.error.withValues(alpha: 0.1),
                  border: Border.all(color: AppColors.error),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  errorMessage,
                  style: AppTypography.bodyMedium.copyWith(
                    color: AppColors.error,
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
            ],
            AppTextField(
              label: 'Email',
              hint: 'vous@example.com',
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
              obscureText: _obscurePassword,
              errorText: _passwordError,
              prefixIcon: Icons.lock_outlined,
            ),
            const SizedBox(height: AppSpacing.md),
            AppTextField(
              label: 'Confirmer le mot de passe',
              controller: _confirmPasswordController,
              obscureText: _obscureConfirmPassword,
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
                const Text(
                  'Vous avez un compte ? ',
                  style: AppTypography.bodyMedium,
                ),
                GestureDetector(
                  onTap: () => context.go(Routes.emailLogin),
                  child: Text(
                    'Connectez-vous',
                    style: AppTypography.labelMedium.copyWith(
                      color: AppColors.primary,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
