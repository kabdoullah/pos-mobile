import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:logger/logger.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../../../core/network/error_mapper.dart';
import '../../../auth/providers/auth_di_providers.dart';
import '../providers/auth_providers.dart';

/// Email login screen.
///
/// Used for account recovery and new device login.
/// Also gateway if PIN not yet configured.
class EmailLoginPage extends ConsumerStatefulWidget {
  /// Creates an email login page.
  const EmailLoginPage({super.key});

  @override
  ConsumerState<EmailLoginPage> createState() => _EmailLoginPageState();
}

class _EmailLoginPageState extends ConsumerState<EmailLoginPage> {
  late TextEditingController _emailController;
  late TextEditingController _passwordController;

  String? _emailError;
  String? _passwordError;

  static final _logger = Logger();

  @override
  void initState() {
    super.initState();
    _emailController = TextEditingController();
    _passwordController = TextEditingController();
    // Clear any stale auth error from previous login attempt.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(authProvider.notifier).clearError();
    });
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  bool _validateForm() {
    _emailError = null;
    _passwordError = null;

    final email = _emailController.text.trim();
    final password = _passwordController.text;

    bool isValid = true;

    if (email.isEmpty) {
      _emailError = 'Email requis';
      isValid = false;
    } else if (!_isValidEmail(email)) {
      _emailError = 'Email invalide';
      isValid = false;
    }

    if (password.isEmpty) {
      _passwordError = 'Mot de passe requis';
      isValid = false;
    }

    setState(() {});
    return isValid;
  }

  bool _isValidEmail(String email) {
    return email.contains('@') && email.contains('.');
  }

  void _showForgotPasswordDialog(BuildContext context) {
    final emailController = TextEditingController(
      text: _emailController.text.trim(),
    );

    unawaited(
      showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Mot de passe oublié'),
          content: TextField(
            controller: emailController,
            keyboardType: TextInputType.emailAddress,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Adresse email',
              hintText: 'votre@email.com',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('Annuler'),
            ),
            TextButton(
              onPressed: () async {
                final email = emailController.text.trim();
                if (email.isEmpty) return;
                Navigator.of(dialogContext).pop();
                try {
                  await ref
                      .read(authRepositoryProvider)
                      .sendPasswordReset(email);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text(
                          'Email envoyé. Vérifiez votre boîte mail.',
                        ),
                        backgroundColor: AppColors.secondary,
                        duration: Duration(seconds: 4),
                      ),
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(errorToFrench(e)),
                        backgroundColor: AppColors.error,
                      ),
                    );
                  }
                }
              },
              child: const Text('Envoyer'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _login() async {
    if (!_validateForm()) return;

    _logger.i('[EmailLogin] Login clicked: ${_emailController.text}');
    try {
      final authNotifier = ref.read(authProvider.notifier);
      _logger.i('[EmailLogin] Calling authNotifier.login()');
      await authNotifier.login(_emailController.text, _passwordController.text);
      _logger.i('[EmailLogin] Login succeeded, router should redirect');
      // Router redirect automatically handles navigation based on new auth state
      // (AuthPinRequired → /pin-login, AuthAuthenticated → /home, etc.)
    } catch (_) {
      // Error state already displayed via authValue.asError in build()
      // No additional error handling needed here — AsyncNotifier stores the message
    }
  }

  @override
  Widget build(BuildContext context) {
    final authValue = ref.watch(authProvider);
    final isLoading = authValue.isLoading;
    final errorMessage = authValue.asError?.error.toString();

    final spacing = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );
    return Scaffold(
      backgroundColor: AppColors.background,
      resizeToAvoidBottomInset: false,
      body: Center(
        child: SingleChildScrollView(
          padding: EdgeInsets.only(
            left: spacing,
            right: spacing,
            top: spacing,
            bottom: spacing + MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const Text('Se connecter', style: AppTypography.titleLarge),
              const SizedBox(height: AppSpacing.xs),
              const Text(
                'Accédez à votre compte POS',
                style: AppTypography.bodyMedium,
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
                controller: _passwordController,
                obscureText: true,
                errorText: _passwordError,
                prefixIcon: Icons.lock_outlined,
              ),
              const SizedBox(height: AppSpacing.sm),
              Align(
                alignment: Alignment.centerRight,
                child: GestureDetector(
                  onTap: () => _showForgotPasswordDialog(context),
                  child: Text(
                    'Mot de passe oublié ?',
                    style: AppTypography.labelMedium.copyWith(
                      color: AppColors.primary,
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              PrimaryButton(
                label: 'Se connecter',
                onPressed: isLoading ? null : _login,
                isLoading: isLoading,
              ),
              const SizedBox(height: AppSpacing.md),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text(
                    'Pas de compte ? ',
                    style: AppTypography.bodyMedium,
                  ),
                  GestureDetector(
                    onTap: () => context.go(Routes.register),
                    child: Text(
                      'Inscrivez-vous',
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
      ),
    );
  }
}
