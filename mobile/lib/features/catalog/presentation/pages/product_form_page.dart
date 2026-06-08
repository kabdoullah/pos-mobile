import 'dart:async';

import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/network/error_mapper.dart';
import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/catalog_providers.dart';

/// Page for creating or editing a product.
class ProductFormPage extends ConsumerStatefulWidget {
  /// Creates a [ProductFormPage].
  const ProductFormPage({super.key, this.productId, this.initialBarcode});

  /// Product ID for edit mode, null for create mode.
  final String? productId;

  /// Barcode pre-filled when navigating from a failed scan lookup.
  final String? initialBarcode;

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
    _barcodeController = TextEditingController(
      text: widget.initialBarcode ?? '',
    );
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
    // ✨ un seul setState — pas de rebuild intermédiaire inutile
    String? nameError;
    String? priceError;

    if (_nameController.text.trim().isEmpty) {
      nameError = 'Le nom est obligatoire';
    }

    if (_priceController.text.trim().isEmpty) {
      priceError = 'Le prix est obligatoire';
    } else if (Decimal.tryParse(_priceController.text.trim()) == null) {
      priceError = 'Entrez un montant valide';
    }

    setState(() {
      _nameError = nameError;
      _priceError = priceError;
    });

    return nameError == null && priceError == null;
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
        ).showSnackBar(SnackBar(content: Text(errorToFrench(e))));
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
        ).showSnackBar(SnackBar(content: Text(errorToFrench(e))));
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
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

    final spacing = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );
    // ✨ AppBar M3 standard — backgroundColor et elevation gérés par le theme
    return Scaffold(
      resizeToAvoidBottomInset: false,
      appBar: AppBar(
        title: Text(isEditMode ? 'Modifier le produit' : 'Nouveau produit'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.only(
            left: spacing,
            right: spacing,
            top: spacing,
            bottom: spacing + MediaQuery.of(context).viewInsets.bottom,
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
                    // ✨ IconButton M3 — remplace Material+InkWell custom (20 lignes → 8)
                    Padding(
                      padding: const EdgeInsets.only(top: AppSpacing.md),
                      child: IconButton(
                        onPressed: _openScanner,
                        icon: const Icon(Icons.qr_code_2, size: 28),
                        tooltip: 'Scanner un code-barres',
                        style: IconButton.styleFrom(
                          backgroundColor: cs.primaryContainer,
                          foregroundColor: cs.onPrimaryContainer,
                        ),
                      ),
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
                  // ✨ cs.error — cs déjà défini en build(), SizedBox fixe supprimé
                  child: OutlinedButton.icon(
                    onPressed: _isLoading ? null : _delete,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Supprimer'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: cs.error,
                      side: BorderSide(color: cs.error),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(
                          AppSpacing.radiusMd,
                        ),
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
    // ✨ une seule CurvedAnimation partagée — évite de créer le même objet deux fois
    final curved = CurvedAnimation(
      parent: animation,
      curve: Interval(delay, delay + 0.4, curve: Curves.easeOut),
    );

    return FadeTransition(
      opacity: Tween<double>(begin: 0, end: 1).animate(curved),
      child: SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0, 0.3),
          end: Offset.zero,
        ).animate(curved),
        child: child,
      ),
    );
  }
}
