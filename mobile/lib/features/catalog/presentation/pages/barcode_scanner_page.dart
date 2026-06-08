import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../shared/widgets/index.dart';

/// Page that displays a barcode scanner and handles camera permission.
class BarcodeScannerPage extends StatefulWidget {
  /// Creates a page for scanning barcodes using the device camera.
  const BarcodeScannerPage({super.key});

  @override
  State<BarcodeScannerPage> createState() => _BarcodeScannerPageState();
}

class _BarcodeScannerPageState extends State<BarcodeScannerPage> {
  late MobileScannerController _controller;
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

  @override
  void dispose() {
    unawaited(_controller.dispose());
    super.dispose();
  }

  Future<void> _checkPermission() async {
    final status = await Permission.camera.request();
    setState(() {
      _isPermissionGranted = status.isGranted;
      _isCheckingPermission = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    // ✨ un seul Scaffold — AppBar M3 standard sans backgroundColor ni elevation hardcodés
    return Scaffold(
      appBar: AppBar(title: const Text('Scanner code-barres')),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    if (_isCheckingPermission) {
      return const Center(child: AppLoadingIndicator());
    }

    if (!_isPermissionGranted) {
      // ✨ EmptyState partagé — supprime ~20 lignes de layout custom redondant
      return const Padding(
        padding: EdgeInsets.all(AppSpacing.lg),
        child: EmptyState(
          icon: Icons.no_photography_outlined,
          title: 'Accès à la caméra refusé',
          message:
              'Pour scanner des codes-barres, autorisez l\'accès à la caméra dans les paramètres.',
          actionLabel: 'Ouvrir les paramètres',
          onAction:
              openAppSettings, // ✨ inline — wrapper _openSettings() supprimé
        ),
      );
    }

    return Stack(
      fit: StackFit.expand,
      children: [
        // Camera feed
        MobileScanner(
          controller: _controller,
          onDetect: (capture) {
            // ✨ firstOrNull — null-safe, évite crash si liste vide
            final code = capture.barcodes.firstOrNull?.rawValue;
            if (code != null && mounted) context.pop(code);
          },
        ),
        // Scrim with viewfinder cutout — evenOdd fill leaves the scan area clear
        const CustomPaint(
          painter: _ScanOverlayPainter(overlayColor: AppColors.scrim),
        ),
        Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SizedBox(
                width: 280,
                height: 280,
                child: CustomPaint(
                  // ✨ couleur via colorScheme — AppColors.primary hardcodé supprimé
                  painter: _ViewfinderPainter(color: cs.secondary),
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              Text(
                'Alignez le code-barres',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: cs.onPrimary, // ✨ onPrimary — texte sur fond sombre
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ScanOverlayPainter extends CustomPainter {
  const _ScanOverlayPainter({required this.overlayColor});

  final Color overlayColor;

  @override
  void paint(Canvas canvas, Size size) {
    const viewfinderSize = 280.0;
    final center = Offset(size.width / 2, size.height / 2);
    final viewfinderRect = Rect.fromCenter(
      center: center,
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

class _ViewfinderPainter extends CustomPainter {
  const _ViewfinderPainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    const cornerLength = 28.0;

    canvas.drawLine(Offset.zero, const Offset(cornerLength, 0), paint);
    canvas.drawLine(Offset.zero, const Offset(0, cornerLength), paint);
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
