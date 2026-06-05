import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
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

  Future<void> _openSettings() async {
    await openAppSettings();
  }

  @override
  Widget build(BuildContext context) {
    if (_isCheckingPermission) {
      return Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(title: const Text('Scanner code-barres')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (!_isPermissionGranted) {
      return Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(title: const Text('Scanner code-barres')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(
                  Icons.no_photography_outlined,
                  size: 64,
                  color: AppColors.error,
                ),
                const SizedBox(height: AppSpacing.lg),
                const Text(
                  'Accès à la caméra refusé',
                  style: AppTypography.titleMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AppSpacing.md),
                const Text(
                  'Pour scanner des codes-barres, autorisez l\'accès à la caméra dans les paramètres.',
                  style: AppTypography.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: AppSpacing.xl),
                PrimaryButton(
                  label: 'Ouvrir les paramètres',
                  onPressed: _openSettings,
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Scanner code-barres'),
        backgroundColor: AppColors.background,
        elevation: 0,
      ),
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Camera feed
          MobileScanner(
            controller: _controller,
            onDetect: (capture) {
              final barcodes = capture.barcodes;
              if (barcodes.isNotEmpty) {
                final code = barcodes.first.rawValue;
                if (code != null && mounted) {
                  context.pop(code);
                }
              }
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
                const SizedBox(
                  width: 280,
                  height: 280,
                  child: CustomPaint(
                    painter: _ViewfinderPainter(color: AppColors.primary),
                  ),
                ),
                const SizedBox(height: AppSpacing.xl),
                Text(
                  'Alignez le code-barres',
                  style: AppTypography.titleMedium.copyWith(
                    color: AppColors.textOnPrimary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
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
