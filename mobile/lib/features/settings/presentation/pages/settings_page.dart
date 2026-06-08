import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../../../../core/router/app_router.dart';
import '../../../../core/sync/sync_orchestrator.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/theme_mode_provider.dart';
import '../../../../shared/widgets/index.dart';
import '../../../auth/presentation/providers/auth_providers.dart';
import '../../../auth/presentation/providers/store_provider.dart';
import '../../../auth/presentation/pages/store_setup_page.dart';
import '../../../printing/presentation/providers/printer_provider.dart';
import '../../../sales/domain/entities/sale.dart';
import '../../../sales/providers/sales_di_providers.dart';
import '../../../sync/presentation/providers/sync_providers.dart';

/// Settings page — store info, printer config, account management.
class SettingsPage extends ConsumerStatefulWidget {
  /// Creates a [SettingsPage].
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  // Guard against double-tap on async actions (concurrent jobs).
  bool _exporting = false;
  bool _syncing = false;

  @override
  Widget build(BuildContext context) {
    final storeAsync = ref.watch(storeConfigProvider);
    final printerState = ref.watch(printerProvider);
    final cs = Theme.of(context).colorScheme;

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
                _SettingsTile(
                  icon: Icons.store_outlined,
                  title: 'Informations boutique',
                  // ✨ état loading explicite plutôt que subtitle vide
                  subtitle: storeAsync.when(
                    loading: () => const Text('Chargement...'),
                    error: (_, _) => const Text('Erreur de chargement'),
                    data: (store) => Text(
                      store?.name ?? 'Non configurée',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  isNavigation: true,
                  onTap: () => Navigator.of(context).push<void>(
                    MaterialPageRoute(
                      fullscreenDialog: true,
                      builder: (_) => const StoreSetupPage(isEditMode: true),
                    ),
                  ),
                ),
              ],
            ),

            // IMPRIMANTE section
            _SettingsSection(
              title: 'IMPRIMANTE',
              children: [
                _SettingsTile(
                  icon: Icons.print_outlined,
                  title: 'Configuration imprimante',
                  subtitle: _printerSubtitle(context, printerState),
                  isNavigation: true,
                  onTap: () => context.push(Routes.bluetoothSetup),
                ),
              ],
            ),

            // DONNÉES section
            _SettingsSection(
              title: 'DONNÉES',
              children: [
                _SettingsTile(
                  icon: Icons.file_download_outlined,
                  title: 'Exporter CSV',
                  subtitle: const Text('Télécharger les ventes'),
                  busy: _exporting,
                  onTap: _exporting ? null : _exportCsv,
                ),
                const Divider(indent: AppSpacing.md, endIndent: AppSpacing.md),
                // ✨ feature à venir — désactivée visuellement, sans SnackBar trompeur
                const _SettingsTile(
                  icon: Icons.picture_as_pdf_outlined,
                  title: 'Exporter PDF',
                  subtitle: Text('Rapport mensuel'),
                  onTap: null,
                  trailingWidget: Chip(
                    label: Text('Bientôt'),
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                    labelPadding: EdgeInsets.symmetric(horizontal: 6),
                  ),
                ),
              ],
            ),

            // SUPPORT section
            _SettingsSection(
              title: 'SUPPORT',
              children: [
                _SettingsTile(
                  icon: Icons.help_outline,
                  title: 'Relancer le tutoriel',
                  subtitle: const Text('Redémarrer la visite guidée'),
                  isNavigation: true,
                  onTap: () => context.push(Routes.tutorial),
                ),
              ],
            ),

            // SAUVEGARDE section
            _SettingsSection(
              title: 'SAUVEGARDE',
              children: [
                _SettingsTile(
                  icon: Icons.cloud_sync_outlined,
                  title: 'Sauvegarder maintenant',
                  subtitle: _syncSubtitle(context),
                  busy: _syncing,
                  // ✨ badge alerte quand des ventes attendent la sync
                  badgeCount: ref.watch(pendingSyncCountProvider).value ?? 0,
                  onTap: _syncing ? null : _handleManualSync,
                ),
              ],
            ),

            // APPARENCE section
            _SettingsSection(
              title: 'APPARENCE',
              children: [
                // ListTile au lieu d'un Row fait main → alignement cohérent
                // avec les autres rangées.
                ListTile(
                  leading: const Icon(Icons.palette_outlined),
                  title: const Text('Thème'),
                  trailing: SegmentedButton<ThemeMode>(
                    segments: const [
                      ButtonSegment(
                        value: ThemeMode.light,
                        icon: Icon(Icons.light_mode_outlined, size: 18),
                        tooltip: 'Clair',
                      ),
                      ButtonSegment(
                        value: ThemeMode.system,
                        icon: Icon(Icons.brightness_auto_outlined, size: 18),
                        tooltip: 'Système',
                      ),
                      ButtonSegment(
                        value: ThemeMode.dark,
                        icon: Icon(Icons.dark_mode_outlined, size: 18),
                        tooltip: 'Sombre',
                      ),
                    ],
                    selected: {ref.watch(themeModeProvider)},
                    onSelectionChanged: (modes) => ref
                        .read(themeModeProvider.notifier)
                        .setMode(modes.first),
                    style: SegmentedButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                  contentPadding: _kTilePadding,
                ),
              ],
            ),

            // COMPTE section
            _SettingsSection(
              title: 'COMPTE',
              children: [
                ListTile(
                  // Couleur via colorScheme → adapte light/dark.
                  leading: Icon(Icons.logout_outlined, color: cs.error),
                  title: Text(
                    'Se déconnecter',
                    style: Theme.of(
                      context,
                    ).textTheme.labelLarge?.copyWith(color: cs.error),
                  ),
                  contentPadding: _kTilePadding,
                  onTap: _confirmLogout,
                ),
              ],
            ),

            const SizedBox(height: AppSpacing.xl),
          ],
        ),
      ),
    );
  }

  Future<void> _confirmLogout() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Se déconnecter'),
        content: const Text('Êtes-vous sûr ?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
              foregroundColor: Theme.of(ctx).colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Déconnecter'),
          ),
        ],
      ),
    );
    if (confirm == true && mounted) {
      unawaited(ref.read(authProvider.notifier).logout());
    }
  }

  // Couleurs theme-aware → s'adaptent au mode sombre.
  Widget? _printerSubtitle(BuildContext context, PrinterState state) {
    final cs = Theme.of(context).colorScheme;
    return switch (state) {
      PrinterConnected(name: final name) => Text(
        name,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: cs.primary,
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
        style: Theme.of(
          context,
        ).textTheme.bodyMedium?.copyWith(color: cs.error),
      ),
      _ => const Text('Non configurée'),
    };
  }

  Widget? _syncSubtitle(BuildContext context) {
    final syncStatus = ref.watch(syncOrchestratorProvider);
    final pendingCount = ref.watch(pendingSyncCountProvider).value ?? 0;

    return switch (syncStatus) {
      SyncStatusSyncing() => const Text('Synchronisation en cours...'),
      SyncStatusError() => Text(
        'Erreur — Réessayer',
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: Theme.of(context).colorScheme.error,
        ),
      ),
      SyncStatusIdle(lastSyncAt: final lastSyncAt) => Text(
        pendingCount > 0
            ? '$pendingCount en attente'
            : lastSyncAt == null
            ? 'Jamais synchronisé'
            // DateFormat locale plutôt qu'une concaténation manuelle.
            : 'Dernière: ${DateFormat('HH:mm').format(lastSyncAt)}',
      ),
    };
  }

  Future<void> _exportCsv() async {
    setState(() => _exporting = true);
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      const SnackBar(
        content: Text('Préparation de l\'export...'),
        duration: Duration(seconds: 30),
        behavior: SnackBarBehavior.floating,
      ),
    );

    try {
      final dir = await getTemporaryDirectory();
      final filename =
          'ventes_${DateFormat('yyyyMMdd').format(DateTime.now())}.csv';
      final file = File('${dir.path}/$filename');
      final sink = file.openWrite();

      sink.writeln('Date,Reçu N°,Total (FCFA),TVA (FCFA),Mode de paiement');

      // Paginate in chunks of 200 to avoid OOM on low-end devices.
      const chunkSize = 200;
      String? cursor;
      while (true) {
        final chunk = await ref
            .read(salesRepositoryProvider)
            .getSales(limit: chunkSize, cursor: cursor);

        for (final sale in chunk) {
          sink.writeln(
            [
              sale.createdAt.toIso8601String(),
              sale.receiptNumber,
              sale.totalAmount,
              sale.vatAmount,
              _paymentMethodLabel(sale.paymentMethod),
            ].join(','),
          );
        }

        if (chunk.length < chunkSize) break;
        cursor = chunk.last.createdAt.toIso8601String();
      }

      await sink.close();

      messenger.hideCurrentSnackBar();

      await SharePlus.instance.share(
        ShareParams(
          files: [XFile(file.path, mimeType: 'text/csv')],
          subject: 'Export ventes POS',
        ),
      );
    } catch (e) {
      messenger.hideCurrentSnackBar();
      if (mounted) {
        messenger.showSnackBar(
          SnackBar(
            content: Text('Erreur export: $e'),
            backgroundColor: Theme.of(context).colorScheme.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _exporting = false);
    }
  }

  static String _paymentMethodLabel(PaymentMethod method) {
    return switch (method) {
      PaymentMethod.cash => 'Espèces',
      PaymentMethod.orangeMoney => 'Orange Money',
      PaymentMethod.mtn => 'MTN',
      PaymentMethod.wave => 'Wave',
      PaymentMethod.mixed => 'Mixte',
    };
  }

  Future<void> _handleManualSync() async {
    setState(() => _syncing = true);
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
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }
}

/// Shared content padding for every settings row (defined once).
const EdgeInsets _kTilePadding = EdgeInsets.symmetric(
  horizontal: AppSpacing.md,
  vertical: AppSpacing.sm,
);

/// Reusable settings row.
///
/// [isNavigation] shows a chevron (true navigation only, never on actions).
/// [busy] swaps the trailing for a spinner and ignores taps.
class _SettingsTile extends StatelessWidget {
  /// Creates a [_SettingsTile].
  const _SettingsTile({
    required this.icon,
    required this.title,
    required this.onTap,
    this.subtitle,
    this.isNavigation = false,
    this.busy = false,
    this.badgeCount = 0,
    this.trailingWidget,
  });

  /// Leading icon.
  final IconData icon;

  /// Row title.
  final String title;

  /// Optional subtitle widget.
  final Widget? subtitle;

  /// Tap callback. Null disables the row.
  final VoidCallback? onTap;

  /// Whether to show a navigation chevron as trailing.
  final bool isNavigation;

  /// Whether an async action is in progress.
  final bool busy;

  /// Badge count on the leading icon — 0 hides the badge.
  final int badgeCount;

  /// Optional trailing widget — overrides built-in chevron/spinner logic.
  final Widget? trailingWidget;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    // ✨ badge M3 sur l'icône pour signaler des éléments en attente
    final Widget leading = badgeCount > 0
        ? Badge(
            label: Text('$badgeCount'),
            child: Icon(icon, color: cs.onSurfaceVariant),
          )
        : Icon(icon, color: cs.onSurfaceVariant);

    final Widget? trailing =
        trailingWidget ??
        (busy
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : isNavigation
            ? Icon(
                Icons.arrow_forward_ios,
                size: 16,
                color: cs.onSurfaceVariant,
              )
            : null);

    return ListTile(
      leading: leading,
      title: Text(title),
      subtitle: subtitle,
      trailing: trailing,
      contentPadding: _kTilePadding,
      onTap: onTap,
    );
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
    // ✨ un seul appel Theme.of(context) — évite la double lookup
    final cs = Theme.of(context).colorScheme;
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
          child: Text(
            title,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: cs.primary,
              letterSpacing: 0.8,
            ),
          ),
        ),
        AppCard(padding: 0, child: Column(children: children)),
      ],
    );
  }
}
