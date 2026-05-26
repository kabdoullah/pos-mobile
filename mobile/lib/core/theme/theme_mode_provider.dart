import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists and exposes the current [ThemeMode].
///
/// Persisted in secure storage (key: `theme_mode`). Falls back to
/// [ThemeMode.system] if no value is stored. State is synchronous so
/// [MaterialApp.themeMode] can consume it directly; the stored value is
/// loaded asynchronously after the first frame.
class ThemeModeNotifier extends Notifier<ThemeMode> {
  static const _key = 'theme_mode';
  static const _storage = FlutterSecureStorage();

  @override
  ThemeMode build() {
    unawaited(_load());
    return ThemeMode.system;
  }

  Future<void> _load() async {
    try {
      final value = await _storage.read(key: _key);
      if (value == null) return;
      final loaded = ThemeMode.values.firstWhere(
        (m) => m.name == value,
        orElse: () => ThemeMode.system,
      );
      state = loaded;
    } catch (_) {}
  }

  /// Updates and persists [mode].
  Future<void> setMode(ThemeMode mode) async {
    state = mode;
    try {
      await _storage.write(key: _key, value: mode.name);
    } catch (_) {}
  }
}

/// Provider for [ThemeModeNotifier].
final themeModeProvider = NotifierProvider<ThemeModeNotifier, ThemeMode>(
  ThemeModeNotifier.new,
);
