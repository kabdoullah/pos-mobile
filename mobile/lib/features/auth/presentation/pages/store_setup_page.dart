import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:logger/logger.dart';

import '../../../../core/network/error_mapper.dart';
import '../../../../core/responsive/responsive.dart';
// ✨ [Design system] import app_colors.dart supprimé — AppColors.textSecondary → cs.onSurfaceVariant
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/auth_providers.dart';
import '../providers/store_provider.dart';
import '../widgets/registration_stepper.dart';
import '../../domain/entities/store.dart';

/// Store setup/configuration page.
///
/// User enters store name, address, optional NCC (tax ID),
/// and TVA status. Happens after first login before accessing main app.
/// Can be used in create mode (after registration) or edit mode (from settings).
class StoreSetupPage extends ConsumerStatefulWidget {
  /// Creates a store setup page.
  const StoreSetupPage({this.isEditMode = false, super.key});

  /// If true, page is in edit mode (from settings) and pops instead of routing.
  final bool isEditMode;

  @override
  ConsumerState<StoreSetupPage> createState() => _StoreSetupPageState();
}

class _StoreSetupPageState extends ConsumerState<StoreSetupPage> {
  static final _logger = Logger();

  late TextEditingController _nameController;
  late TextEditingController _addressController;
  late TextEditingController _nccController;

  String? _nameError;
  bool _isSubjectToVat = true;
  bool _isLoading = false;

  /// True once the edit-mode form has been pre-filled from the existing store.
  /// Guards against overwriting user edits if the provider re-emits.
  bool _prefilled = false;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController();
    _addressController = TextEditingController();
    _nccController = TextEditingController();
  }

  /// Pre-fills the form from the store once its data is available.
  ///
  /// Handles the async race where `storeConfigProvider` is still loading on
  /// first build: called both from the initial `ref.read` and from a
  /// `ref.listen` so a late-arriving value still populates the fields.
  void _prefillFrom(AsyncValue<Store?> async) {
    if (_prefilled) return;
    final store = async.asData?.value;
    if (store == null) return;
    _prefilled = true;
    _nameController.text = store.name;
    _addressController.text = store.address ?? '';
    _nccController.text = store.ncc ?? '';
    // Defer setState out of the build phase (this may run during build).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) setState(() => _isSubjectToVat = store.isSubjectToVat);
    });
  }

  @override
  void dispose() {
    _nameController.dispose();
    _addressController.dispose();
    _nccController.dispose();
    super.dispose();
  }

  bool _validateForm() {
    _nameError = null;
    final name = _nameController.text.trim();

    if (name.isEmpty) {
      _nameError = 'Nom de la boutique requis';
    }

    setState(() {});
    return _nameError == null;
  }

  Future<void> _saveStore() async {
    if (!_validateForm()) return;

    setState(() => _isLoading = true);

    try {
      final store = Store(
        name: _nameController.text.trim(),
        address: _addressController.text.trim().isEmpty
            ? null
            : _addressController.text.trim(),
        ncc: _nccController.text.trim().isEmpty
            ? null
            : _nccController.text.trim(),
        isSubjectToVat: _isSubjectToVat,
        receiptFooterText: null,
      );

      await ref.read(storeConfigProvider.notifier).save(store);

      // Bail out if the widget was unmounted during the save.
      if (!mounted) {
        _logger.w('Widget not mounted after save');
        return;
      }

      setState(() => _isLoading = false);

      if (widget.isEditMode) {
        // Edit mode is opened via showModalBottomSheet (root Navigator),
        // not go_router — pop the Flutter Navigator, not the router.
        Navigator.of(context).pop();
      } else {
        _logger.i('Calling proceedToPinSetup()');
        await ref.read(authProvider.notifier).proceedToPinSetup();
        _logger.i('proceedToPinSetup() completed');
      }
    } catch (e) {
      if (mounted) {
        _logger.e('Error saving store configuration - $e');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              errorToFrench(e),
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onError,
              ),
            ),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Edit mode: pre-fill from the existing store, handling the case where the
    // provider is still loading on first build (listen catches late values).
    if (widget.isEditMode && !_prefilled) {
      ref.listen<AsyncValue<Store?>>(storeConfigProvider, (_, next) {
        _prefillFrom(next);
      });
      _prefillFrom(ref.read(storeConfigProvider));
    }

    // ✨ [Qualité] colorScheme centralisé — supprime les Theme.of(context) inline répétés
    final cs = Theme.of(context).colorScheme;
    final spacing = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );

    return Scaffold(
      // Edit mode is pushed as a fullscreen dialog from settings — give it a
      // close affordance. Create mode is reached via the router and has no
      // back action (onboarding step), so it keeps its in-body header only.
      appBar: widget.isEditMode
          ? AppBar(
              elevation: 0,
              leading: IconButton(
                icon: const Icon(Icons.close),
                // ✨ [A11y] tooltip — obligatoire sur tous les IconButton (WCAG 2.4.6)
                tooltip: 'Fermer',
                onPressed: () => Navigator.of(context).pop(),
              ),
            )
          : null,
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (!widget.isEditMode)
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
                    const RegistrationStepper(currentStep: 2),
                    const SizedBox(height: AppSpacing.lg),
                    // ✨ [Design system] explicit cs.onSurface — cohérence avec register_page.dart
                    Text(
                      'Votre boutique',
                      style: AppTypography.titleLarge.copyWith(
                        color: cs.onSurface,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    // ✨ [Design system] cs.onSurfaceVariant remplace AppColors.textSecondary — dark mode safe
                    Text(
                      'Configurez votre point de vente pour vos reçus et rapports.',
                      style: AppTypography.bodyMedium.copyWith(
                        color: cs.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              )
            else
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
                    // ✨ [Design system] explicit cs.onSurface — cohérence inter-pages
                    Text(
                      'Modifier ma boutique',
                      style: AppTypography.titleLarge.copyWith(
                        color: cs.onSurface,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      'Informations de votre commerce',
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
                    AppTextField(
                      label: 'Nom de la boutique',
                      hint: 'ex: Ma boutique',
                      controller: _nameController,
                      errorText: _nameError,
                      prefixIcon: Icons.storefront_outlined,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AppTextField(
                      label: 'Adresse (optionnel)',
                      hint: 'ex: 123 rue du Commerce',
                      controller: _addressController,
                      prefixIcon: Icons.location_on_outlined,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AppTextField(
                      label: 'NCC (optionnel)',
                      hint: 'Numéro de contribuable',
                      controller: _nccController,
                      prefixIcon: Icons.badge_outlined,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Padding(
                      padding: const EdgeInsets.only(left: AppSpacing.md),
                      child: Row(
                        children: [
                          // ✨ [A11y] ExcludeSemantics — icône décorative, le texte suffit
                          ExcludeSemantics(
                            child: Icon(
                              Icons.help_outline,
                              size: 16,
                              color: cs.onSurfaceVariant,
                            ),
                          ),
                          const SizedBox(width: AppSpacing.xs),
                          Expanded(
                            // ✨ [Design system] cs.onSurfaceVariant explicite — visuel subordonné
                            child: Text(
                              'Numéro attribué par les autorités fiscales pour la facturation',
                              style: AppTypography.captionText.copyWith(
                                color: cs.onSurfaceVariant,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Container(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      decoration: BoxDecoration(
                        color: cs.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
                      ),
                      // ✨ [A11y] MergeSemantics — associe "Assujetti à la TVA" au Switch
                      //    pour que VoiceOver/TalkBack lise un seul élément cohérent
                      child: MergeSemantics(
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Assujetti à la TVA',
                                  style: AppTypography.labelMedium,
                                ),
                                SizedBox(height: AppSpacing.xs),
                                Text(
                                  'Votre boutique facture avec TVA',
                                  style: AppTypography.captionText,
                                ),
                              ],
                            ),
                            Switch(
                              value: _isSubjectToVat,
                              onChanged: (value) {
                                setState(() => _isSubjectToVat = value);
                              },
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    PrimaryButton(
                      label: 'Enregistrer ma boutique',
                      onPressed: _isLoading ? null : _saveStore,
                      isLoading: _isLoading,
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
