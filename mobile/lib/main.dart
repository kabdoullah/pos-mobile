import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'core/app.dart';
import 'core/config.dart';
import 'core/network/network_providers.dart';

/// Point d'entrée dev — flavor "dev", API staging.
///
/// Pour la prod, utiliser main_prod.dart avec `--flavor prod`.
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  AppConfig.setup(
    flavor: AppFlavor.dev,
    apiUrl: 'http://192.168.1.121:8000',
  );
  await initializeDateFormatting('fr_FR');
  runApp(
    ProviderScope(
      overrides: [
        tokenStorageProvider.overrideWith(
          (ref) => ref.watch(secureTokenStorageProvider),
        ),
      ],
      child: const PosMobileApp(),
    ),
  );
}
