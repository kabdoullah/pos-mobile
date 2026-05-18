import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../domain/entities/cart_item.dart';
import '../providers/cart_provider.dart';
import '../providers/scan_provider.dart';

/// NewSalePage — permanent scanner with cart bottom sheet overlay.
class NewSalePage extends ConsumerStatefulWidget {
  const NewSalePage({super.key});

  @override
  ConsumerState<NewSalePage> createState() => _NewSalePageState();
}

class _NewSalePageState extends ConsumerState<NewSalePage> {
  late final MobileScannerController _controller;
  bool _isCameraActive = false;
  bool _isTorchOn = false;
  bool _isPermissionGranted = false;
  bool _isCheckingPermission = true;

  @override
  void initState() {
    super.initState();
    _controller = MobileScannerController(
      detectionSpeed: DetectionSpeed.noDuplicates,
      facing: CameraFacing.back,
      torchEnabled: false,
    );
    unawaited(_checkPermission());
  }

  Future<void> _checkPermission() async {
    final status = await Permission.camera.request();
    if (!mounted) return;
    setState(() {
      _isPermissionGranted = status.isGranted;
      _isCheckingPermission = false;
      _isCameraActive = status.isGranted;
    });
  }

  void _enableCamera() {
    setState(() => _isCameraActive = true);
  }

  void _disableCamera() {
    setState(() {
      _isCameraActive = false;
      _isTorchOn = false;
    });
  }

  Future<void> _toggleTorch() async {
    await _controller.toggleTorch();
    if (!mounted) return;
    setState(() => _isTorchOn = !_isTorchOn);
  }

  void _updateQuantity(String productId, int qty) {
    ref.read(cartProvider.notifier).updateQuantity(productId, qty);
  }

  void _removeItem(String productId) {
    ref.read(cartProvider.notifier).removeItem(productId);
  }

  Future<void> _checkout() async {
    final wasActive = _isCameraActive;
    if (wasActive) {
      setState(() => _isCameraActive = false);
      await WidgetsBinding.instance.endOfFrame;
    }
    if (!mounted) return;
    await context.push(Routes.payment);
    if (wasActive && mounted && _isPermissionGranted) {
      setState(() => _isCameraActive = true);
    }
  }

  Future<void> _onBarcodeDetected(BarcodeCapture capture) async {
    final code = capture.barcodes.firstOrNull?.rawValue;
    if (code == null || !mounted) return;

    final result = await ref.read(scanControllerProvider.notifier).scan(code);

    if (result == ScanResult.cooldown) return;

    if (result == ScanResult.added ||
        result == ScanResult.quantityIncremented) {
      unawaited(HapticFeedback.mediumImpact());
      return;
    }

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Produit introuvable : $code'),
          action: SnackBarAction(
            label: 'Ajouter au catalogue',
            onPressed: () => context.push(Routes.productNew),
          ),
        ),
      );
    }
  }

  @override
  void dispose() {
    unawaited(_controller.dispose());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cartState = ref.watch(cartProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final availableHeight = constraints.maxHeight;
            const overlapDp = 24.0;
            final scannerHeight = availableHeight * 0.4 + overlapDp;
            final cartTop = availableHeight * 0.4 - overlapDp;

            return Stack(
              children: [
                // Scanner panel
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  height: scannerHeight,
                  child: _ScannerPanel(
                    controller: _controller,
                    isCameraActive: _isCameraActive,
                    isTorchOn: _isTorchOn,
                    isPermissionGranted: _isPermissionGranted,
                    isCheckingPermission: _isCheckingPermission,
                    onBarcodeDetected: _onBarcodeDetected,
                    onEnableCamera: _enableCamera,
                    onDisableCamera: _disableCamera,
                    onToggleTorch: _toggleTorch,
                    onOpenSettings: () => context.push(Routes.settings),
                    onBack: () => context.pop(),
                    onOpenAppSettings: () => openAppSettings(),
                  ),
                ),
                // Cart panel overlapping the scanner
                Positioned(
                  top: cartTop,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  child: _CartPanel(
                    cartState: cartState,
                    onUpdateQuantity: _updateQuantity,
                    onRemoveItem: _removeItem,
                    onCheckout: _checkout,
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _ScannerPanel extends StatelessWidget {
  const _ScannerPanel({
    required this.controller,
    required this.isCameraActive,
    required this.isTorchOn,
    required this.isPermissionGranted,
    required this.isCheckingPermission,
    required this.onBarcodeDetected,
    required this.onEnableCamera,
    required this.onDisableCamera,
    required this.onToggleTorch,
    required this.onOpenSettings,
    required this.onBack,
    required this.onOpenAppSettings,
  });
  final MobileScannerController controller;
  final bool isCameraActive;
  final bool isTorchOn;
  final bool isPermissionGranted;
  final bool isCheckingPermission;
  final void Function(BarcodeCapture) onBarcodeDetected;
  final VoidCallback onEnableCamera;
  final VoidCallback onDisableCamera;
  final VoidCallback onToggleTorch;
  final VoidCallback onOpenSettings;
  final VoidCallback onBack;
  final VoidCallback onOpenAppSettings;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (isCheckingPermission)
            _buildLoadingState()
          else if (!isPermissionGranted)
            _buildPermissionDeniedState()
          else if (isCameraActive)
            _buildActiveCamera()
          else
            _buildCameraOffState(),
          _buildFloatingButtons(),
        ],
      ),
    );
  }

  Widget _buildLoadingState() {
    return Container(
      color: AppColors.cameraBackground,
      child: const Center(child: AppLoadingIndicator()),
    );
  }

  Widget _buildPermissionDeniedState() {
    return Container(
      color: AppColors.cameraBackground,
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: EmptyState(
        icon: Icons.no_photography_outlined,
        title: 'Accès caméra refusé',
        message: 'Autorisez l\'accès à la caméra dans les paramètres.',
        actionLabel: 'Ouvrir les paramètres',
        onAction: onOpenAppSettings,
      ),
    );
  }

  Widget _buildCameraOffState() {
    return Container(
      color: AppColors.cameraBackground,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.videocam_off_outlined,
            size: 48,
            color: AppColors.textDisabled,
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            'Caméra éteinte',
            style: AppTypography.titleMedium.copyWith(
              color: AppColors.textDisabled,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
            child: SecondaryButton(
              label: 'Activer la caméra',
              onPressed: onEnableCamera,
              icon: Icons.videocam_outlined,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActiveCamera() {
    return Stack(
      fit: StackFit.expand,
      children: [
        MobileScanner(controller: controller, onDetect: onBarcodeDetected),
        const CustomPaint(
          painter: _ScannerOverlayPainter(overlayColor: AppColors.scrim),
        ),
        const Center(
          child: SizedBox(
            width: 200,
            height: 200,
            child: CustomPaint(
              painter: _ViewfinderCornersPainter(color: AppColors.secondary),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFloatingButtons() {
    return Stack(
      children: [
        Positioned(
          top: AppSpacing.sm,
          left: AppSpacing.sm,
          child: _FloatingIconButton(icon: Icons.arrow_back, onPressed: onBack),
        ),
        Positioned(
          top: AppSpacing.sm,
          right: AppSpacing.sm,
          child: Column(
            children: [
              _FloatingIconButton(
                icon: Icons.settings_outlined,
                onPressed: onOpenSettings,
              ),
              const SizedBox(height: AppSpacing.sm),
              if (isPermissionGranted && !isCheckingPermission) ...[
                _FloatingIconButton(
                  icon: isTorchOn ? Icons.flashlight_off : Icons.flashlight_on,
                  onPressed: isCameraActive ? onToggleTorch : null,
                ),
                const SizedBox(height: AppSpacing.sm),
                _FloatingIconButton(
                  icon: isCameraActive ? Icons.videocam : Icons.videocam_off,
                  onPressed: isCameraActive ? onDisableCamera : onEnableCamera,
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _FloatingIconButton extends StatelessWidget {
  const _FloatingIconButton({required this.icon, this.onPressed});
  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surface.withValues(alpha: 0.85),
      borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
        child: SizedBox(
          width: AppSpacing.iconButtonSize,
          height: AppSpacing.iconButtonSize,
          child: Icon(
            icon,
            color: onPressed != null
                ? AppColors.textPrimary
                : AppColors.textDisabled,
            size: 22,
          ),
        ),
      ),
    );
  }
}

class _CartPanel extends StatelessWidget {
  const _CartPanel({
    required this.cartState,
    required this.onUpdateQuantity,
    required this.onRemoveItem,
    required this.onCheckout,
  });
  final CartState cartState;
  final void Function(String productId, int qty) onUpdateQuantity;
  final void Function(String productId) onRemoveItem;
  final VoidCallback onCheckout;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(AppSpacing.radiusLg),
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.scrim,
            blurRadius: 8,
            offset: Offset(0, -2),
          ),
        ],
      ),
      child: Column(
        children: [
          const SizedBox(height: AppSpacing.sm),
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.border,
                borderRadius: BorderRadius.circular(AppSpacing.radiusFull),
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Articles scannés',
                        style: AppTypography.labelMedium,
                      ),
                      Text(
                        '${cartState.itemCount} article${cartState.itemCount > 1 ? 's' : ''}',
                        style: AppTypography.bodySmall,
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    const Text('TOTAL', style: AppTypography.labelSmall),
                    AmountDisplay(
                      amount: cartState.total,
                      size: AmountSize.hero,
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          const Divider(height: 1, color: AppColors.divider),
          Expanded(
            child: cartState.isEmpty
                ? const EmptyState(
                    icon: Icons.shopping_cart_outlined,
                    title: 'Votre panier est vide',
                    message:
                        'Scannez un produit avec la caméra ci-dessus pour commencer',
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.md,
                      vertical: AppSpacing.sm,
                    ),
                    itemCount: cartState.items.length,
                    itemBuilder: (context, index) {
                      final item = cartState.items[index];
                      return Dismissible(
                        key: ValueKey(item.productId),
                        direction: DismissDirection.endToStart,
                        onDismissed: (_) => onRemoveItem(item.productId),
                        background: Container(
                          color: AppColors.error,
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: AppSpacing.md),
                          child: const Icon(
                            Icons.delete,
                            color: AppColors.textOnPrimary,
                          ),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                          child: _CartItemRow(
                            item: item,
                            onDecrease: () => onUpdateQuantity(
                              item.productId,
                              item.quantity - 1,
                            ),
                            onIncrease: () => onUpdateQuantity(
                              item.productId,
                              item.quantity + 1,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              AppSpacing.sm,
              AppSpacing.md,
              AppSpacing.md,
            ),
            child: PrimaryButton(
              label: 'Encaisser',
              onPressed: cartState.isEmpty ? null : onCheckout,
              icon: Icons.point_of_sale,
            ),
          ),
        ],
      ),
    );
  }
}

class _CartItemRow extends StatelessWidget {
  const _CartItemRow({
    required this.item,
    required this.onDecrease,
    required this.onIncrease,
  });
  final CartItem item;
  final VoidCallback onDecrease;
  final VoidCallback onIncrease;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item.productName,
                  style: AppTypography.titleMedium,
                  overflow: TextOverflow.ellipsis,
                  maxLines: 1,
                ),
                const SizedBox(height: AppSpacing.xs),
                AmountDisplay(amount: item.unitPrice, size: AmountSize.small),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              AmountDisplay(amount: item.lineTotal, size: AmountSize.large),
              const SizedBox(height: AppSpacing.xs),
              Row(
                children: [
                  _QuantityButton(icon: Icons.remove, onTap: onDecrease),
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.sm,
                    ),
                    child: Text(
                      '${item.quantity}',
                      style: AppTypography.titleMedium,
                    ),
                  ),
                  _QuantityButton(icon: Icons.add, onTap: onIncrease),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _QuantityButton extends StatelessWidget {
  const _QuantityButton({required this.icon, required this.onTap});
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 32,
        height: 32,
        decoration: BoxDecoration(
          color: AppColors.primaryContainer,
          borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
        ),
        child: Icon(icon, size: 16, color: AppColors.primary),
      ),
    );
  }
}

class _ScannerOverlayPainter extends CustomPainter {
  const _ScannerOverlayPainter({required this.overlayColor});
  final Color overlayColor;

  @override
  void paint(Canvas canvas, Size size) {
    const viewfinderSize = 200.0;
    final cx = size.width / 2;
    final cy = size.height / 2;
    final viewfinderRect = Rect.fromCenter(
      center: Offset(cx, cy),
      width: viewfinderSize,
      height: viewfinderSize,
    );

    final path = Path()
      ..addRect(Rect.fromLTWH(0, 0, size.width, size.height))
      ..addRRect(
        RRect.fromRectAndRadius(viewfinderRect, const Radius.circular(12)),
      )
      ..fillType = PathFillType.evenOdd;

    canvas.drawPath(path, Paint()..color = overlayColor);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _ViewfinderCornersPainter extends CustomPainter {
  const _ViewfinderCornersPainter({required this.color});
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    const cornerLength = 24.0;

    // Top-left
    canvas.drawLine(Offset.zero, const Offset(cornerLength, 0), paint);
    canvas.drawLine(Offset.zero, const Offset(0, cornerLength), paint);

    // Top-right
    canvas.drawLine(
      Offset(size.width, 0),
      Offset(size.width - cornerLength, 0),
      paint,
    );
    canvas.drawLine(
      Offset(size.width, 0),
      Offset(size.width, cornerLength),
      paint,
    );

    // Bottom-left
    canvas.drawLine(
      Offset(0, size.height),
      Offset(cornerLength, size.height),
      paint,
    );
    canvas.drawLine(
      Offset(0, size.height),
      Offset(0, size.height - cornerLength),
      paint,
    );

    // Bottom-right
    canvas.drawLine(
      Offset(size.width, size.height),
      Offset(size.width - cornerLength, size.height),
      paint,
    );
    canvas.drawLine(
      Offset(size.width, size.height),
      Offset(size.width, size.height - cornerLength),
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
