import 'package:app_settings/app_settings.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:print_bluetooth_thermal/print_bluetooth_thermal.dart';

import '../../../../core/responsive/responsive.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../shared/widgets/index.dart';
import '../providers/printer_provider.dart';

/// Page for pairing and connecting to a Bluetooth thermal printer.
///
/// The page explains that printers must be paired in Android system settings first,
/// then lists paired devices for selection and connection.
class BluetoothSetupPage extends ConsumerStatefulWidget {
  /// Creates a [BluetoothSetupPage].
  const BluetoothSetupPage({super.key});

  @override
  ConsumerState<BluetoothSetupPage> createState() => _BluetoothSetupPageState();
}

class _BluetoothSetupPageState extends ConsumerState<BluetoothSetupPage> {
  bool _hasPermission = false;
  bool _checkingPermission = true;
  List<BluetoothInfo> _pairedDevices = [];
  bool _isLoading = false;
  // ✨ track quel MAC est en cours de connexion — évite le spinner global sur tous les devices
  String? _connectingMac;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkPermissions());
  }

  Future<void> _checkPermissions() async {
    // Check BLUETOOTH_CONNECT permission (Android 12+)
    final status = await Permission.bluetoothConnect.status;
    final hasPermission = status.isGranted;

    if (mounted) {
      setState(() {
        _hasPermission = hasPermission;
        _checkingPermission = false;
      });
    }

    if (hasPermission) {
      await _loadDevices();
    }
  }

  Future<void> _requestPermission() async {
    final result = await Permission.bluetoothConnect.request();
    if (result.isGranted) {
      if (mounted) setState(() => _hasPermission = true);
      await _loadDevices();
    } else if (result.isDenied) {
      if (mounted) setState(() => _checkingPermission = false);
    } else if (result.isPermanentlyDenied) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Permission refusée. Ouvre les paramètres de l\'app.',
            ),
            duration: Duration(seconds: 3),
          ),
        );
        await AppSettings.openAppSettings();
      }
    }
  }

  Future<void> _loadDevices() async {
    if (_isLoading) return;

    setState(() => _isLoading = true);
    try {
      // Note: BluetoothInfo.macAdress has a typo (single 'd') in print_bluetooth_thermal v1.2.x
      final devices = await PrintBluetoothThermal.pairedBluetooths;
      if (mounted) setState(() => _pairedDevices = devices);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Erreur: ${e.toString()}'),
            backgroundColor: Theme.of(context).colorScheme.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _connectToDevice(BluetoothInfo device) async {
    if (ref.read(printerProvider) is PrinterConnecting) return;

    // ✨ mémoriser le MAC pour afficher le spinner uniquement sur cette carte
    setState(() => _connectingMac = device.macAdress);

    // Note: BluetoothInfo.macAdress (single 'd')
    await ref
        .read(printerProvider.notifier)
        .connect(device.macAdress, device.name);

    if (!mounted) return;
    setState(() => _connectingMac = null);

    final newState = ref.read(printerProvider);
    if (newState is PrinterConnected) {
      _onConnectSuccess();
    } else if (newState is PrinterError) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Erreur: ${newState.message}'),
          backgroundColor: Theme.of(context).colorScheme.error,
        ),
      );
    }
  }

  // Fix #2: show snackbar + pop instead of broken test-print dialog
  void _onConnectSuccess() {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('Imprimante connectée avec succès'),
        backgroundColor: Theme.of(context).colorScheme.secondary,
        duration: const Duration(seconds: 2),
      ),
    );
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    // ✨ extraits une fois — pas de double lookup Theme.of(context) dans itemBuilder
    final cs = Theme.of(context).colorScheme;
    final tt = Theme.of(context).textTheme;

    return AppScaffold(
      title: 'Configurer l\'imprimante',
      actions: [
        if (!_checkingPermission && _hasPermission)
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadDevices,
            tooltip: 'Actualiser',
          ),
      ],
      body: SingleChildScrollView(
        padding: EdgeInsets.all(
          responsiveValue(context, small: AppSpacing.md, medium: AppSpacing.lg),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_checkingPermission) ...[
              const Center(child: AppLoadingIndicator()),
              const SizedBox(height: AppSpacing.lg),
              const Text(
                'Vérification des permissions...',
                textAlign: TextAlign.center,
              ),
            ] else if (!_hasPermission) ...[
              EmptyState(
                icon: Icons.bluetooth_disabled_outlined,
                title: 'Permission Bluetooth requise',
                message:
                    'L\'app doit accéder à Bluetooth pour découvrir les imprimantes.',
                actionLabel: 'Accorder la permission',
                onAction: _requestPermission,
              ),
            ] else if (_pairedDevices.isEmpty) ...[
              EmptyState(
                icon: Icons.print_outlined,
                title: 'Aucune imprimante trouvée',
                message:
                    'Appairez d\'abord votre imprimante Bluetooth dans les réglages Android.',
                actionLabel: 'Ouvrir les réglages Bluetooth',
                // Fix #3: open Bluetooth settings directly via app_settings
                onAction: () => AppSettings.openAppSettings(
                  type: AppSettingsType.bluetooth,
                ),
              ),
            ] else ...[
              // ✨ barre de progression lors d'un refresh (liste déjà visible)
              if (_isLoading) const LinearProgressIndicator(),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Appareils appairés (${_pairedDevices.length})',
                style: tt.titleSmall,
              ),
              const SizedBox(height: AppSpacing.md),
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _pairedDevices.length,
                separatorBuilder: (_, _) =>
                    const SizedBox(height: AppSpacing.sm),
                itemBuilder: (context, index) {
                  final device = _pairedDevices[index];
                  final printerState = ref.watch(printerProvider);
                  final isConnected =
                      printerState is PrinterConnected &&
                      printerState.mac == device.macAdress;
                  final isAnyConnecting = printerState is PrinterConnecting;
                  // ✨ spinner uniquement sur LA carte du device en cours de connexion
                  final isThisDeviceConnecting =
                      _connectingMac == device.macAdress;

                  return AppCard(
                    onTap: (isConnected || isAnyConnecting)
                        ? null
                        : () => _connectToDevice(device),
                    child: ListTile(
                      leading: Icon(
                        isConnected ? Icons.check_circle : Icons.bluetooth,
                        color: isConnected ? cs.secondary : cs.onSurfaceVariant,
                      ),
                      title: Text(device.name),
                      subtitle: Text(device.macAdress, style: tt.bodySmall),
                      trailing: isConnected
                          ? Text(
                              'Connectée',
                              style: tt.bodyMedium?.copyWith(
                                color: cs.secondary,
                                fontWeight: FontWeight.w500,
                              ),
                            )
                          : isThisDeviceConnecting
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : Icon(
                              Icons.arrow_forward_ios,
                              size: 16,
                              color: cs.onSurfaceVariant,
                            ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.md,
                        vertical: AppSpacing.xs,
                      ),
                    ),
                  );
                },
              ),
            ],
          ],
        ),
      ),
    );
  }
}
