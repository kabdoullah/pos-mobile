import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/date_symbol_data_local.dart';

import 'core/app.dart';
import 'core/network/network_providers.dart';

void main() async {
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
