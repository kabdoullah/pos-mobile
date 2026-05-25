import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'sync_status_indicator.dart';

/// Standard app scaffold with optional offline banner.
///
/// Displays a yellow warning banner when offline to notify users
/// that their actions will be synced when connectivity returns.
/// Bottom navigation is handled by MainShell for authenticated routes.
class AppScaffold extends ConsumerWidget {
  /// Creates an app scaffold.
  const AppScaffold({
    required this.title,
    required this.body,
    this.actions,
    this.floatingActionButton,
    this.showOfflineBanner = true,
    super.key,
  });

  /// AppBar title.
  final String title;

  /// Main content of the scaffold.
  final Widget body;

  /// Actions to display in the AppBar.
  final List<Widget>? actions;

  /// Floating action button widget.
  final Widget? floatingActionButton;

  /// Whether to show offline banner when disconnected.
  final bool showOfflineBanner;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      appBar: AppBar(title: Text(title), actions: actions),
      body: Column(
        children: [
          if (showOfflineBanner) const SyncStatusIndicator(),
          Expanded(child: body),
        ],
      ),
      floatingActionButton: floatingActionButton,
    );
  }
}
