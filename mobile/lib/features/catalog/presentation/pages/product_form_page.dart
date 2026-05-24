import 'dart:async';

import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/catalog_providers.dart';

/// Page for creating or editing a product.
class ProductFormPage extends ConsumerStatefulWidget {
  /// Creates a [ProductFormPage].
  const ProductFormPage({super.key, this.productId});

  /// Product ID for edit mode, null for create mode.
  final String? productId;

  @override
  ConsumerState<ProductFormPage> createState() => _ProductFormPageState();
}

class _ProductFormPageState extends ConsumerState<ProductFormPage>
    with TickerProviderStateMixin {
  late TextEditingController _nameController;
  late TextEditingController _priceController;
  late TextEditingController _barcodeController;
  late TextEditingController _stockController;
  late AnimationController _formAnimationController;
  String? _nameError;
  String? _priceError;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController();
    _priceController = TextEditingController();
    _barcodeController = TextEditingController();
    _stockController = TextEditingController();
    _formAnimationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    unawaited(_formAnimationController.forward());
  }

  @override
  void dispose() {
    _nameController.dispose();
    _priceController.dispose();
    _barcodeController.dispose();
    _stockController.dispose();
    _formAnimationController.dispose();
    super.dispose();
  }

  Future<void> _openScanner() async {
    final code = await context.push<String>(Routes.barcodeScanner);
    if (code != null && mounted) {
      _barcodeController.text = code;
    }
  }

  bool _validate() {
    bool isValid = true;
    setState(() {
      _nameError = null;
      _priceError = null;
    });

    if (_nameController.text.trim().isEmpty) {
      setState(() => _nameError = 'Le nom est obligatoire');
      isValid = false;
    }

    if (_priceController.text.trim().isEmpty) {
      setState(() => _priceError = 'Le prix est obligatoire');
      isValid = false;
    } else {
      if (Decimal.tryParse(_priceController.text.trim()) == null) {
        setState(() => _priceError = 'Entrez un montant valide');
        isValid = false;
      }
    }

    return isValid;
  }

  Future<void> _submit() async {
    if (!_validate()) return;

    setState(() => _isLoading = true);

    try {
      final name = _nameController.text.trim();
      final price = _priceController.text.trim();
      final barcode = _barcodeController.text.trim();
      final stock = _stockController.text.trim().isEmpty
          ? null
          : int.parse(_stockController.text.trim());

      if (widget.productId == null) {
        // Create mode
        await ref
            .read(catalogListProvider.notifier)
            .createProduct(
              name: name,
              unitPrice: price,
              barcode: barcode.isEmpty ? null : barcode,
              currentStock: stock,
            );
      } else {
        // Edit mode
        await ref
            .read(catalogListProvider.notifier)
            .updateProduct(
              id: widget.productId!,
              name: name,
              unitPrice: price,
              barcode: barcode.isEmpty ? null : barcode,
              currentStock: stock,
            );
      }

      if (mounted) {
        context.pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Erreur: $e')));
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _delete() async {
    if (widget.productId == null) return;

    final confirmed = await showConfirmDialog(
      context,
      title: 'Supprimer le produit',
      message: 'Êtes-vous sûr? Cette action ne peut pas être annulée.',
      confirmLabel: 'Supprimer',
      isDangerous: true,
    );

    if (!confirmed) return;

    setState(() => _isLoading = true);

    try {
      await ref
          .read(catalogListProvider.notifier)
          .deleteProduct(widget.productId!);
      if (mounted) {
        context.pop();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Erreur: $e')));
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEditMode = widget.productId != null;
    final productAsync = isEditMode
        ? ref.watch(productProvider(widget.productId!))
        : null;

    // Load form data when in edit mode
    if (productAsync != null) {
      productAsync.whenData((product) {
        if (product != null &&
            _nameController.text.isEmpty &&
            _priceController.text.isEmpty) {
          _nameController.text = product.name;
          _priceController.text = product.unitPrice.toString();
          if (product.barcode != null) {
            _barcodeController.text = product.barcode!;
          }
          if (product.currentStock != null) {
            _stockController.text = product.currentStock!.toString();
          }
        }
      });
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(isEditMode ? 'Modifier le produit' : 'Nouveau produit'),
        elevation: 0,
      ),
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
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _AnimatedFormField(
                animation: _formAnimationController,
                delay: 0.0,
                child: AppTextField(
                  label: 'Nom du produit',
                  hint: 'ex: Riz blanc',
                  controller: _nameController,
                  errorText: _nameError,
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              _AnimatedFormField(
                animation: _formAnimationController,
                delay: 0.1,
                child: AppTextField(
                  label: 'Prix unitaire (FCFA)',
                  hint: '0',
                  controller: _priceController,
                  keyboardType: TextInputType.number,
                  errorText: _priceError,
                  prefixIcon: Icons.attach_money,
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              _AnimatedFormField(
                animation: _formAnimationController,
                delay: 0.2,
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: AppTextField(
                        label: 'Code-barres',
                        hint: 'Optionnel',
                        controller: _barcodeController,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.md),
                    Column(
                      children: [
                        const SizedBox(height: AppSpacing.md),
                        GestureDetector(
                          onTap: _openScanner,
                          child: Container(
                            padding: const EdgeInsets.all(AppSpacing.md),
                            decoration: BoxDecoration(
                              color: AppColors.primaryContainer,
                              borderRadius: BorderRadius.circular(
                                AppSpacing.radiusMd,
                              ),
                            ),
                            child: const Icon(
                              Icons.qr_code_2,
                              color: AppColors.primary,
                              size: 28,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              _AnimatedFormField(
                animation: _formAnimationController,
                delay: 0.3,
                child: AppTextField(
                  label: 'Stock initial',
                  hint: 'Optionnel',
                  controller: _stockController,
                  keyboardType: TextInputType.number,
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              _AnimatedFormField(
                animation: _formAnimationController,
                delay: 0.4,
                child: PrimaryButton(
                  label: isEditMode ? 'Modifier' : 'Enregistrer',
                  onPressed: _isLoading ? null : _submit,
                  isLoading: _isLoading,
                ),
              ),
              if (isEditMode) ...[
                const SizedBox(height: AppSpacing.md),
                _AnimatedFormField(
                  animation: _formAnimationController,
                  delay: 0.5,
                  child: GestureDetector(
                    onTap: _isLoading ? null : _delete,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        vertical: AppSpacing.md,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.errorContainer,
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
                        border: Border.all(color: AppColors.error, width: 1),
                      ),
                      child: Text(
                        'Supprimer',
                        style: AppTypography.labelLarge.copyWith(
                          color: AppColors.error,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Private animated form field wrapper — fades and slides in on load.
class _AnimatedFormField extends StatelessWidget {
  const _AnimatedFormField({
    required this.animation,
    required this.delay,
    required this.child,
  });

  final AnimationController animation;
  final double delay;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final delayedAnimation = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(
        parent: animation,
        curve: Interval(delay, delay + 0.4, curve: Curves.easeOut),
      ),
    );

    return FadeTransition(
      opacity: delayedAnimation,
      child: SlideTransition(
        position: Tween<Offset>(begin: const Offset(0, 0.3), end: Offset.zero)
            .animate(
              CurvedAnimation(
                parent: animation,
                curve: Interval(delay, delay + 0.4, curve: Curves.easeOut),
              ),
            ),
        child: child,
      ),
    );
  }
}
