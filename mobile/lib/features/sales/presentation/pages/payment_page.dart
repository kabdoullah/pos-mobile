import 'package:decimal/decimal.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../../core/network/error_mapper.dart';
import '../../../../core/responsive/responsive.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../domain/entities/sale.dart';
import '../../domain/entities/cart_item.dart';
import '../providers/cart_provider.dart';
import '../providers/sales_providers.dart';

/// PaymentPage — payment method selection and change calculation.
class PaymentPage extends ConsumerStatefulWidget {
  /// Creates a [PaymentPage].
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
    if (_selectedMethod == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Sélectionnez un mode de paiement')),
      );
      return false;
    }

    // ✨ un seul setState — compute errors first, then render once
    String? cashError;
    String? mobileError;
    var isValid = true;

    if (_selectedMethod == PaymentMethod.cash) {
      final text = _cashReceivedController.text.trim();
      if (text.isEmpty) {
        cashError = 'Entrez le montant reçu';
        isValid = false;
      } else {
        final received = Decimal.tryParse(text);
        if (received == null) {
          cashError = 'Montant invalide';
          isValid = false;
        } else if (received < _getCartTotal()) {
          cashError = 'Montant insuffisant';
          isValid = false;
        }
      }
    } else if (_selectedMethod == PaymentMethod.mixed) {
      final hasCash = _cashReceivedController.text.trim().isNotEmpty;
      final hasMobileMoney = _mobileMoneyController.text.trim().isNotEmpty;

      if (!hasCash && !hasMobileMoney) {
        cashError = 'Entrez au moins un montant';
        mobileError = 'Entrez au moins un montant';
        isValid = false;
      } else {
        var total = Decimal.zero;
        if (hasCash) {
          final cash = Decimal.tryParse(_cashReceivedController.text.trim());
          if (cash == null) {
            cashError = 'Montant invalide';
            isValid = false;
          } else {
            total += cash;
          }
        }
        if (hasMobileMoney) {
          final mm = Decimal.tryParse(_mobileMoneyController.text.trim());
          if (mm == null) {
            mobileError = 'Montant invalide';
            isValid = false;
          } else {
            total += mm;
          }
        }
        if (isValid && total != _getCartTotal()) {
          final formatted = NumberFormat(
            '#,##0',
            'fr_FR',
          ).format(_getCartTotal().toDouble());
          cashError = 'Total doit être $formatted FCFA';
          mobileError = 'Total doit être $formatted FCFA';
          isValid = false;
        }
      }
    }

    setState(() {
      _cashReceivedError = cashError;
      _mobileMoneyError = mobileError;
    });

    return isValid;
  }

  Future<void> _submit() async {
    if (!_validate()) return;

    setState(() => _isSubmitting = true);

    try {
      // Snapshot items BEFORE submitSale clears the cart
      final items = List<CartItem>.from(ref.read(cartProvider).items);

      final method = _selectedMethod!;
      final total = _getCartTotal();
      final vat =
          Decimal.zero; // TVA non appliquée au MVP (pas de taux par produit)

      Decimal? cashAmount;
      Decimal? mobileMoneyAmount;
      if (method == PaymentMethod.mixed) {
        if (_cashReceivedController.text.trim().isNotEmpty) {
          cashAmount = Decimal.tryParse(_cashReceivedController.text.trim());
        }
        if (_mobileMoneyController.text.trim().isNotEmpty) {
          mobileMoneyAmount = Decimal.tryParse(
            _mobileMoneyController.text.trim(),
          );
        }
      }

      final sale = await ref.read(
        submitSaleProvider(
          totalAmount: total,
          vatAmount: vat,
          paymentMethod: method,
          cashAmount: cashAmount,
          mobileMoneyAmount: mobileMoneyAmount,
        ).future,
      );

      // ✨ vider le panier ici — submitSaleProvider (auto-dispose) peut être
      // disposé pendant l'await, rendant ref.mounted false et skippant le clear
      ref.read(cartProvider.notifier).clear();

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
        ).showSnackBar(SnackBar(content: Text(errorToFrench(e))));
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

    final spacing = responsiveValue(
      context,
      small: AppSpacing.md,
      medium: AppSpacing.lg,
    );
    // ✨ backgroundColor géré par le thème M3 — AppColors.background supprimé
    return Scaffold(
      resizeToAvoidBottomInset: false,
      appBar: AppBar(title: const Text('Paiement')),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: EdgeInsets.only(
                left: spacing,
                right: spacing,
                top: spacing,
                bottom: spacing,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Total to pay
                  AppCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Total à payer',
                          style: AppTypography.bodySmall,
                        ),
                        const SizedBox(height: AppSpacing.sm),
                        // ✨ texte vide supprimé — amount seul, aligné à droite
                        Align(
                          alignment: Alignment.centerRight,
                          child: AmountDisplay(
                            amount: total,
                            size: AmountSize.hero,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  // Payment methods — compact chips to keep input fields visible
                  const Text(
                    'Mode de paiement',
                    style: AppTypography.titleMedium,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  _buildMethodSelector(),
                  const SizedBox(height: AppSpacing.sm),
                  // Dynamic fields based on payment method
                  if (_selectedMethod == PaymentMethod.cash) ...[
                    AppTextField(
                      label: 'Montant reçu (FCFA)',
                      controller: _cashReceivedController,
                      keyboardType: TextInputType.number,
                      errorText: _cashReceivedError,
                      onChanged: (_) => setState(() {}),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    if (change > Decimal.zero)
                      AppCard(
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Monnaie à rendre',
                              style: AppTypography.titleMedium,
                            ),
                            AmountDisplay(
                              amount: change,
                              size: AmountSize.large,
                            ),
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
                ],
              ),
            ),
          ),
          Padding(
            padding: EdgeInsets.only(
              left: spacing,
              right: spacing,
              bottom: spacing + MediaQuery.of(context).viewInsets.bottom,
              top: spacing,
            ),
            child: PrimaryButton(
              label: 'Valider la vente',
              onPressed: _isSubmitting ? null : _submit,
              isLoading: _isSubmitting,
            ),
          ),
        ],
      ),
    );
  }

  static const _paymentMethods = [
    (
      method: PaymentMethod.cash,
      label: 'Espèces',
      icon: Icons.payments_outlined,
    ),
    (
      method: PaymentMethod.orangeMoney,
      label: 'Orange Money',
      icon: Icons.smartphone_outlined,
    ),
    (method: PaymentMethod.mtn, label: 'MTN', icon: Icons.phone_android),
    (method: PaymentMethod.wave, label: 'Wave', icon: Icons.contactless),
    (method: PaymentMethod.mixed, label: 'Mixte', icon: Icons.multiple_stop),
  ];

  Widget _buildMethodSelector() {
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm,
      children: _paymentMethods.map((entry) {
        final isSelected = _selectedMethod == entry.method;
        return ChoiceChip(
          avatar: Icon(entry.icon, size: 18),
          label: Text(entry.label),
          selected: isSelected,
          onSelected: (_) => _selectMethod(entry.method),
          showCheckmark: false,
        );
      }).toList(),
    );
  }
}
