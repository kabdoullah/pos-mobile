import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/app.dart';

void main() {
  // Configuration globale ici si besoin (orientation, system UI, etc.)
  runApp(const ProviderScope(child: PosMobileApp()));
}
