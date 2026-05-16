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
  final bool _obscurePassword = true;

  @override
  void initState() {
    super.initState();
    _emailController = TextEditingController();
    _passwordController = TextEditingController();
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

  Future<void> _login() async {
    if (!_validateForm()) return;

    try {
      final authNotifier = ref.read(authProvider.notifier);
      await authNotifier.login(_emailController.text, _passwordController.text);
      // Router redirect automatically handles navigation based on new auth state
      // (AuthStatePinRequired → /pin-login, AuthStateAuthenticated → /home, etc.)
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Erreur: ${e.toString()}',
              style: const TextStyle(color: AppColors.textOnPrimary),
            ),
            backgroundColor: AppColors.error,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final isLoading = authState is AuthStateLoading;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Connexion'), elevation: 0),
      body: SingleChildScrollView(
        padding: EdgeInsets.all(
          responsiveValue(context, small: AppSpacing.md, medium: AppSpacing.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Se connecter', style: AppTypography.titleLarge),
            const SizedBox(height: AppSpacing.xs),
            const Text(
              'Accédez à votre compte POS',
              style: AppTypography.bodyMedium,
            ),
            const SizedBox(height: AppSpacing.lg),
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
              obscureText: _obscurePassword,
              errorText: _passwordError,
              prefixIcon: Icons.lock_outlined,
            ),
            const SizedBox(height: AppSpacing.sm),
            Align(
              alignment: Alignment.centerRight,
              child: GestureDetector(
                onTap: () {
                  // TODO: Implement password reset flow.
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Réinitialisation de mot de passe (à venir)',
                      ),
                    ),
                  );
                },
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
                const Text('Pas de compte ? ', style: AppTypography.bodyMedium),
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
    );
  }
}
