import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/sync/sync_orchestrator.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../shared/widgets/index.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../auth/presentation/providers/store_provider.dart';
import '../../../auth/presentation/pages/store_setup_page.dart';
import '../../../printing/presentation/providers/printer_provider.dart';
import '../../../sync/presentation/providers/sync_providers.dart';

/// Settings page — store info, printer config, account management.
class SettingsPage extends ConsumerWidget {
  /// Creates a [SettingsPage].
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final storeAsync = ref.watch(storeConfigProvider);
    final printerState = ref.watch(printerProvider);

    return AppScaffold(
      title: 'Paramètres',
      body: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // MA BOUTIQUE section
            _SettingsSection(
              title: 'MA BOUTIQUE',
              children: [
                ListTile(
                  leading: const Icon(Icons.store_outlined),
                  title: const Text('Informations boutique'),
                  subtitle: storeAsync.whenOrNull(
                    data: (store) => Text(
                      store?.name ?? 'Non configurée',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () => showModalBottomSheet(
                    context: context,
                    isScrollControlled: true,
                    builder: (_) => const StoreSetupPage(isEditMode: true),
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
              ],
            ),

            // IMPRIMANTE section
            _SettingsSection(
              title: 'IMPRIMANTE',
              children: [
                ListTile(
                  leading: const Icon(Icons.print_outlined),
                  title: const Text('Configuration imprimante'),
                  subtitle: _getPrinterSubtitle(printerState),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () => context.push(Routes.bluetoothSetup),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
              ],
            ),

            // DONNÉES section
            _SettingsSection(
              title: 'DONNÉES',
              children: [
                ListTile(
                  leading: const Icon(Icons.file_download_outlined),
                  title: const Text('Exporter CSV'),
                  subtitle: const Text('Télécharger les ventes'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () {
                    // TODO: Implement CSV export from Drift
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Bientôt disponible')),
                    );
                  },
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
                const Divider(indent: AppSpacing.md, endIndent: AppSpacing.md),
                ListTile(
                  leading: const Icon(Icons.picture_as_pdf_outlined),
                  title: const Text('Exporter PDF'),
                  subtitle: const Text('Rapport mensuel'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Bientôt disponible')),
                    );
                  },
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
              ],
            ),

            // SUPPORT section
            _SettingsSection(
              title: 'SUPPORT',
              children: [
                ListTile(
                  leading: const Icon(Icons.message_outlined),
                  title: const Text('Support WhatsApp'),
                  subtitle: const Text('Contacter l\'équipe'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () async {
                    // TODO: Replace with actual support number
                    final uri = Uri.parse('https://wa.me/225XXXXXXXXXX');
                    if (await canLaunchUrl(uri)) {
                      await launchUrl(uri);
                    }
                  },
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
                const Divider(indent: AppSpacing.md, endIndent: AppSpacing.md),
                ListTile(
                  leading: const Icon(Icons.help_outline),
                  title: const Text('Relancer le tutoriel'),
                  subtitle: const Text('Redémarrer la visite guidée'),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () => context.push(Routes.tutorial),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
              ],
            ),

            // SAUVEGARDE section
            _SettingsSection(
              title: 'SAUVEGARDE',
              children: [
                ListTile(
                  leading: const Icon(Icons.cloud_sync_outlined),
                  title: const Text('Sauvegarder maintenant'),
                  subtitle: _getSyncSubtitle(ref),
                  trailing: const Icon(Icons.arrow_forward_ios, size: 16),
                  onTap: () => _handleManualSync(context, ref),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                ),
              ],
            ),

            // COMPTE section
            _SettingsSection(
              title: 'COMPTE',
              children: [
                ListTile(
                  leading: Icon(Icons.logout_outlined, color: AppColors.error),
                  title: Text(
                    'Se déconnecter',
                    style: AppTypography.labelLarge.copyWith(
                      color: AppColors.error,
                    ),
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                    vertical: AppSpacing.sm,
                  ),
                  onTap: () async {
                    final confirm = await showConfirmDialog(
                      context,
                      title: 'Se déconnecter',
                      message: 'Êtes-vous sûr ?',
                      confirmLabel: 'Déconnecter',
                      cancelLabel: 'Annuler',
                      isDangerous: true,
                    );
                    if (confirm && context.mounted) {
                      ref.read(authProvider.notifier).logout();
                    }
                  },
                ),
              ],
            ),

            const SizedBox(height: AppSpacing.xl),
          ],
        ),
      ),
    );
  }

  static Widget? _getPrinterSubtitle(PrinterState state) {
    return switch (state) {
      PrinterConnected(name: final name) => Text(
        name,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(
          color: AppColors.secondary,
          fontWeight: FontWeight.w500,
        ),
      ),
      PrinterDisconnected(savedName: final name) => Text(
        name == null ? 'Aucune imprimante' : 'Prête: $name',
      ),
      PrinterError(message: final msg) => Text(
        'Erreur: $msg',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(color: AppColors.error),
      ),
      _ => const Text('Non configurée'),
    };
  }

  static Widget? _getSyncSubtitle(WidgetRef ref) {
    final syncStatus = ref.watch(syncOrchestratorProvider);
    final pendingCount = ref.watch(pendingSyncCountProvider).value ?? 0;

    return switch (syncStatus) {
      SyncStatusSyncing() => const Text('Synchronisation en cours...'),
      SyncStatusError() => const Text(
        'Erreur — Réessayer',
        style: TextStyle(color: AppColors.error),
      ),
      SyncStatusIdle(lastSyncAt: final lastSyncAt) => Text(
        pendingCount > 0
            ? '$pendingCount en attente'
            : lastSyncAt == null
            ? 'Jamais synchronisé'
            : 'Dernière: ${lastSyncAt.hour}:${lastSyncAt.minute.toString().padLeft(2, '0')}',
      ),
    };
  }

  static Future<void> _handleManualSync(
    BuildContext context,
    WidgetRef ref,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    final orchestrator = ref.read(syncOrchestratorProvider.notifier);

    messenger.showSnackBar(
      const SnackBar(
        content: Text('Sauvegarde en cours...'),
        duration: Duration(seconds: 60),
        behavior: SnackBarBehavior.floating,
      ),
    );

    try {
      await orchestrator.syncNow();
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        const SnackBar(
          content: Text('Tout est sauvegardé'),
          duration: Duration(seconds: 2),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (e) {
      messenger.hideCurrentSnackBar();
      messenger.showSnackBar(
        const SnackBar(
          content: Text('Erreur de sauvegarde — réessayez'),
          duration: Duration(seconds: 3),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }
}

/// Private settings section widget.
class _SettingsSection extends StatelessWidget {
  /// Creates a [_SettingsSection].
  const _SettingsSection({required this.title, required this.children});

  /// Section title.
  final String title;

  /// Section content widgets.
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.md,
            AppSpacing.lg,
            AppSpacing.md,
            AppSpacing.md,
          ),
          child: Text(title, style: AppTypography.labelLarge),
        ),
        AppCard(padding: 0, child: Column(children: children)),
      ],
    );
  }
}
