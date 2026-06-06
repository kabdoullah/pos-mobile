import 'package:flutter/material.dart';
import 'package:flutter_native_splash/flutter_native_splash.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/theme/app_colors.dart';
import '../../presentation/providers/auth_providers.dart';

/// Handles initial routing after app launch.
///
/// Renders an invisible placeholder while the native splash is shown.
/// Removes the native splash when auth state resolves; the router's
/// `ref.listen` in `appRouter` then triggers the appropriate redirect.
class SplashPage extends ConsumerWidget {
  /// Creates a splash page.
  const SplashPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Remove native splash when auth transitions from loading → resolved.
    ref.listen(authProvider, (previous, next) {
      if (previous?.isLoading == true && !next.isLoading) {
        FlutterNativeSplash.remove();
      }
    });

    // Edge case: auth already resolved on first build (hot reload, fast init).
    if (!ref.watch(authProvider).isLoading) {
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => FlutterNativeSplash.remove(),
      );
    }

    // Native splash covers this entirely. Color matches background to avoid
    // a flash on the single frame between remove() and router redirect.
    return const ColoredBox(color: AppColors.background);
  }
}
