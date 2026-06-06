import 'package:flutter/foundation.dart';
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

  static final ThemeData _lightTheme = AppTheme.light();
  static final ThemeData _darkTheme = AppTheme.dark();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Keeps SyncOrchestrator alive without triggering rebuilds on sync state changes.
    ref.listen(syncOrchestratorProvider, (_, _) {});

    final router = ref.watch(appRouterProvider);
    final themeMode = ref.watch(themeModeProvider);

    return MaterialApp.router(
      title: 'POS Mobile',
      theme: _lightTheme,
      darkTheme: _darkTheme,
      themeMode: themeMode,
      routerConfig: router,
      debugShowCheckedModeBanner: kDebugMode,
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
