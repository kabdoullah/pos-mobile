import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'sync/sync_orchestrator.dart';
import 'theme.dart';
import 'theme/theme_mode_provider.dart';
import 'router/app_router.dart';

/// Root application widget.
class PosMobileApp extends ConsumerWidget {
  /// Constructor.
  const PosMobileApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Initialize sync orchestrator (monitors connectivity, triggers periodic syncs).
    ref.watch(syncOrchestratorProvider);

    final router = ref.watch(appRouterProvider);
    final themeMode = ref.watch(themeModeProvider);

    return MaterialApp.router(
      title: 'POS Mobile',
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: themeMode,
      routerConfig: router,
      debugShowCheckedModeBanner: false,
      builder: (context, child) {
        return GestureDetector(
          behavior: HitTestBehavior.translucent,
          onTap: () {
            FocusScope.of(context).unfocus();
          },
          child: child ?? const SizedBox.shrink(),
        );
      },
    );
  }
}
