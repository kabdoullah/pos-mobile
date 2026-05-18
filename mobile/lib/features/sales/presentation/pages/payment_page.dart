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
import '../../domain/entities/sale.dart';
import '../../domain/entities/cart_item.dart';
import '../providers/cart_provider.dart';
import '../providers/sales_providers.dart';

/// PaymentPage — payment method selection and change calculation.
class PaymentPage extends ConsumerStatefulWidget {
  const PaymentPage({super.key});

  @override
  ConsumerState<PaymentPage> createState() => _PaymentPageState();
}

class _PaymentPageState extends ConsumerState<PaymentPage> {
  PaymentMethod? _selectedMethod;
  late TextEditingController _cashReceivedController;
  late TextEditingController _mobileMoneyController;
  String? _cashReceivedError;
  String? _mobileMoneyError;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _cashReceivedController = TextEditingController();
    _mobileMoneyController = TextEditingController();
  }

  @override
  void dispose() {
    _cashReceivedController.dispose();
    _mobileMoneyController.dispose();
    super.dispose();
  }

  void _selectMethod(PaymentMethod method) {
    setState(() {
      _selectedMethod = method;
      _cashReceivedError = null;
      _mobileMoneyError = null;
    });
  }

  Decimal _getCartTotal() {
    return ref.read(cartProvider).total;
  }

  Decimal _getChangeAmount() {
    if (_selectedMethod != PaymentMethod.cash) return Decimal.zero;
    final received = Decimal.tryParse(_cashReceivedController.text.trim());
    if (received == null) return Decimal.zero;
    return received - _getCartTotal();
  }

  bool _validate() {
    bool isValid = true;
    setState(() {
      _cashReceivedError = null;
      _mobileMoneyError = null;
    });

    if (_selectedMethod == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Sélectionnez un mode de paiement')),
      );
      return false;
    }

    if (_selectedMethod == PaymentMethod.cash) {
      if (_cashReceivedController.text.trim().isEmpty) {
        setState(() => _cashReceivedError = 'Entrez le montant reçu');
        isValid = false;
      } else {
        final received = Decimal.tryParse(_cashReceivedController.text.trim());
        if (received == null) {
          setState(() => _cashReceivedError = 'Montant invalide');
          isValid = false;
        } else if (received < _getCartTotal()) {
          setState(() => _cashReceivedError = 'Montant insuffisant');
          isValid = false;
        }
      }
    } else if (_selectedMethod == PaymentMethod.mixed) {
      final hasCash = _cashReceivedController.text.trim().isNotEmpty;
      final hasMobileMoney = _mobileMoneyController.text.trim().isNotEmpty;

      if (!hasCash && !hasMobileMoney) {
        setState(() {
          _cashReceivedError = 'Entrez au moins un montant';
          _mobileMoneyError = 'Entrez au moins un montant';
        });
        isValid = false;
      } else {
        var total = Decimal.zero;
        if (hasCash) {
          final cash = Decimal.tryParse(_cashReceivedController.text.trim());
          if (cash == null) {
            setState(() => _cashReceivedError = 'Montant invalide');
            isValid = false;
          } else {
            total += cash;
          }
        }
        if (hasMobileMoney) {
          final mm = Decimal.tryParse(_mobileMoneyController.text.trim());
          if (mm == null) {
            setState(() => _mobileMoneyError = 'Montant invalide');
            isValid = false;
          } else {
            total += mm;
          }
        }
        if (isValid && total != _getCartTotal()) {
          setState(() {
            _cashReceivedError = 'Total doit égaler ${_getCartTotal()} FCFA';
            _mobileMoneyError = 'Total doit égaler ${_getCartTotal()} FCFA';
          });
          isValid = false;
        }
      }
    }

    return isValid;
  }

  Future<void> _submit() async {
    if (!_validate()) return;

    setState(() => _isSubmitting = true);

    try {
      // Snapshot items BEFORE submitSale clears the cart
      final items = List<CartItem>.from(ref.read(cartProvider).items);

      final method = _selectedMethod!;
      final total = _getCartTotal().toString();
      const vat = '0'; // TODO: Calculate VAT from cart

      final sale = await ref.read(
        submitSaleProvider(
          totalAmount: total,
          vatAmount: vat,
          paymentMethod: method,
        ).future,
      );

      if (mounted) {
        // Navigate to success screen with sale and items
        context.pushReplacement(
          Routes.saleSuccess,
          extra: (sale: sale, items: items),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Erreur: $e')));
      }
    } finally {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final total = _getCartTotal();
    final change = _getChangeAmount();

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(title: const Text('Paiement'), elevation: 0),
      body: SingleChildScrollView(
        padding: EdgeInsets.all(
          responsiveValue(context, small: AppSpacing.md, medium: AppSpacing.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Total to pay
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Total à payer', style: AppTypography.bodySmall),
                  const SizedBox(height: AppSpacing.sm),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(''),
                      AmountDisplay(amount: total, size: AmountSize.hero),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xl),
            // Payment methods
            const Text('Mode de paiement', style: AppTypography.titleMedium),
            const SizedBox(height: AppSpacing.md),
            _buildPaymentMethodButton(
              PaymentMethod.cash,
              'Espèces',
              Icons.payments,
            ),
            const SizedBox(height: AppSpacing.md),
            _buildPaymentMethodButton(
              PaymentMethod.orangeMoney,
              'Orange Money',
              Icons.phone_android,
            ),
            const SizedBox(height: AppSpacing.md),
            _buildPaymentMethodButton(
              PaymentMethod.mtn,
              'MTN',
              Icons.phone_android,
            ),
            const SizedBox(height: AppSpacing.md),
            _buildPaymentMethodButton(
              PaymentMethod.wave,
              'Wave',
              Icons.phone_android,
            ),
            const SizedBox(height: AppSpacing.md),
            _buildPaymentMethodButton(
              PaymentMethod.mixed,
              'Mixte',
              Icons.multiple_stop,
            ),
            const SizedBox(height: AppSpacing.xl),
            // Dynamic fields based on payment method
            if (_selectedMethod == PaymentMethod.cash) ...[
              AppTextField(
                label: 'Montant reçu (FCFA)',
                controller: _cashReceivedController,
                keyboardType: TextInputType.number,
                errorText: _cashReceivedError,
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: AppSpacing.lg),
              if (change > Decimal.zero)
                AppCard(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Monnaie à rendre',
                        style: AppTypography.titleMedium,
                      ),
                      AmountDisplay(amount: change, size: AmountSize.large),
                    ],
                  ),
                ),
            ] else if (_selectedMethod == PaymentMethod.mixed) ...[
              AppTextField(
                label: 'Espèces (FCFA)',
                controller: _cashReceivedController,
                keyboardType: TextInputType.number,
                errorText: _cashReceivedError,
                onChanged: (_) => setState(() {}),
              ),
              const SizedBox(height: AppSpacing.md),
              AppTextField(
                label: 'Mobile Money (FCFA)',
                controller: _mobileMoneyController,
                keyboardType: TextInputType.number,
                errorText: _mobileMoneyError,
                onChanged: (_) => setState(() {}),
              ),
            ],
            const SizedBox(height: AppSpacing.xl),
            PrimaryButton(
              label: 'Valider la vente',
              onPressed: _isSubmitting ? null : _submit,
              isLoading: _isSubmitting,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPaymentMethodButton(
    PaymentMethod method,
    String label,
    IconData icon,
  ) {
    final isSelected = _selectedMethod == method;
    return GestureDetector(
      onTap: () => _selectMethod(method),
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primaryContainer : AppColors.surface,
          border: Border.all(
            color: isSelected ? AppColors.primary : AppColors.border,
            width: isSelected ? 2 : 1,
          ),
          borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              color: isSelected ? AppColors.primary : AppColors.textPrimary,
              size: 28,
            ),
            const SizedBox(width: AppSpacing.md),
            Text(
              label,
              style: AppTypography.titleMedium.copyWith(
                color: isSelected ? AppColors.primary : AppColors.textPrimary,
              ),
            ),
            const Spacer(),
            if (isSelected) const Icon(Icons.check_circle, color: AppColors.primary),
          ],
        ),
      ),
    );
  }
}
