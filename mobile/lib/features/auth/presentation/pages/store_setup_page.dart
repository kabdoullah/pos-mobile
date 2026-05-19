import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/store_provider.dart';
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
  late TextEditingController _nameController;
  late TextEditingController _addressController;
  late TextEditingController _nccController;

  String? _nameError;
  bool _isSubjectToVat = true;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController();
    _addressController = TextEditingController();
    _nccController = TextEditingController();

    // Pre-fill form if editing existing store
    if (widget.isEditMode) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _loadExistingStore());
    }
  }

  Future<void> _loadExistingStore() async {
    final storeAsync = ref.read(storeConfigProvider);
    storeAsync.whenData((store) {
      if (store != null && mounted) {
        _nameController.text = store.name;
        _addressController.text = store.address ?? '';
        _nccController.text = store.ncc ?? '';
        setState(() => _isSubjectToVat = store.isSubjectToVat);
      }
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

      if (mounted) {
        if (widget.isEditMode) {
          context.pop();
        } else {
          context.go(Routes.tutorial);
        }
      }
    } catch (e) {
      if (mounted) {
        final message = e is NetworkException ? e.message : e.toString();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Erreur: $message',
              style: const TextStyle(color: AppColors.textOnPrimary),
            ),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Configuration'), elevation: 0),
      body: SingleChildScrollView(
        padding: EdgeInsets.all(
          responsiveValue(context, small: AppSpacing.md, medium: AppSpacing.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Enregistrer ma boutique',
              style: AppTypography.titleLarge,
            ),
            const SizedBox(height: AppSpacing.xs),
            const Text(
              'Informations de votre commerce',
              style: AppTypography.bodyMedium,
            ),
            const SizedBox(height: AppSpacing.lg),
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
              prefixIcon: Icons.card_giftcard_outlined,
            ),
            const SizedBox(height: AppSpacing.sm),
            const Padding(
              padding: EdgeInsets.only(left: AppSpacing.md),
              child: Row(
                children: [
                  Icon(
                    Icons.help_outline,
                    size: 16,
                    color: AppColors.textSecondary,
                  ),
                  SizedBox(width: AppSpacing.xs),
                  Expanded(
                    child: Text(
                      'Numéro attribué par les autorités fiscales pour la facturation',
                      style: AppTypography.captionText,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            Container(
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: AppColors.surfaceVariant,
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              ),
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
                    activeThumbColor: AppColors.primary,
                  ),
                ],
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
    );
  }
}
