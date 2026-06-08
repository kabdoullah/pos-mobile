import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:logger/logger.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../shared/widgets/index.dart';
import '../../../../core/network/error_mapper.dart';
import '../../../../core/utils/phone_formatter.dart';
import '../../../auth/providers/auth_di_providers.dart';
import '../providers/auth_providers.dart';

/// Phone number login screen (primary authentication).
///
/// Also entry point for new device login and account recovery via forgot-password dialog.
class PhoneLoginPage extends ConsumerStatefulWidget {
  /// Creates a phone login page.
  const PhoneLoginPage({super.key});

  @override
  ConsumerState<PhoneLoginPage> createState() => _PhoneLoginPageState();
}

class _PhoneLoginPageState extends ConsumerState<PhoneLoginPage> {
  late TextEditingController _phoneController;
  late TextEditingController _passwordController;

  String? _phoneError;
  String? _passwordError;

  static final _logger = Logger();

  @override
  void initState() {
    super.initState();
    _phoneController = TextEditingController();
    _passwordController = TextEditingController();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) ref.read(authProvider.notifier).clearError();
    });
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  bool _validateForm() {
    _phoneError = null;
    _passwordError = null;

    final phone = _phoneController.text.trim();
    final password = _passwordController.text;

    bool isValid = true;

    if (phone.isEmpty) {
      _phoneError = 'Numéro requis';
      isValid = false;
    } else if (!isValidLocalPhoneCi(phone)) {
      _phoneError = 'Format invalide. Ex: 07 00 00 00 00';
      isValid = false;
    }

    if (password.isEmpty) {
      _passwordError = 'Mot de passe requis';
      isValid = false;
    }

    setState(() {});
    return isValid;
  }

  void _showForgotPasswordDialog(BuildContext context) {
    final emailController = TextEditingController();

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
              labelText: 'Adresse email de récupération',
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
                    final cs = Theme.of(context).colorScheme;
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: const Text(
                          'Email envoyé. Vérifiez votre boîte mail.',
                        ),
                        backgroundColor: cs.secondaryContainer,
                        duration: const Duration(seconds: 4),
                      ),
                    );
                  }
                } catch (e) {
                  if (context.mounted) {
                    final cs = Theme.of(context).colorScheme;
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(errorToFrench(e)),
                        backgroundColor: cs.error,
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

    final e164 = toE164Ci(_phoneController.text.trim())!;
    _logger.i('[PhoneLogin] Login clicked: $e164');
    await ref
        .read(authProvider.notifier)
        .login(e164, _passwordController.text);
    if (ref.read(authProvider) is AsyncData) {
      _logger.i('[PhoneLogin] Login succeeded, router should redirect');
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;
    final authValue = ref.watch(authProvider);
    final isLoading = authValue.isLoading;
    final errorMessage = authValue.asError?.error.toString();

    final spacing = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );

    return Scaffold(
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
              // ✨ Hero icon — ancre visuelle inspirée du design de référence
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  color: cs.primaryContainer,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
                ),
                child: Icon(
                  Icons.lock_open_outlined,
                  size: 36,
                  color: cs.onPrimaryContainer,
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              Text('Se connecter', style: tt.titleLarge),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Accédez à votre espace marchand',
                style: tt.bodyMedium?.copyWith(color: cs.onSurfaceVariant),
              ),
              const SizedBox(height: AppSpacing.lg),
              // ✨ AnimatedSwitcher + liveRegion — cohérent avec RegisterPage
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 200),
                child: errorMessage != null
                    ? Semantics(
                        liveRegion: true,
                        key: ValueKey(errorMessage),
                        child: Container(
                          width: double.infinity,
                          margin: const EdgeInsets.only(bottom: AppSpacing.lg),
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
                                Icons.error_outline_rounded,
                                color: cs.onErrorContainer,
                                size: 20,
                              ),
                              const SizedBox(width: AppSpacing.sm),
                              Expanded(
                                child: Text(
                                  errorMessage,
                                  style: tt.bodyMedium?.copyWith(
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
                label: 'Téléphone',
                hint: '07 00 00 00 00',
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                inputFormatters: const [SpacedPhoneFormatter()],
                errorText: _phoneError,
                prefixIcon: Icons.phone_outlined,
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
                child: TextButton(
                  onPressed: () => _showForgotPasswordDialog(context),
                  child: const Text('Mot de passe oublié ?'),
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              PrimaryButton(
                label: 'Se connecter',
                trailingIcon: Icons.arrow_forward_rounded,
                onPressed: isLoading ? null : _login,
                isLoading: isLoading,
              ),
              const SizedBox(height: AppSpacing.md),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text('Pas de compte ? ', style: tt.bodyMedium),
                  TextButton(
                    onPressed: () => context.go(Routes.register),
                    child: const Text('Inscrivez-vous'),
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
