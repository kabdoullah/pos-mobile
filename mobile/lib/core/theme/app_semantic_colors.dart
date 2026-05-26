import 'package:flutter/material.dart';

/// App-specific semantic colors not covered by Material 3 [ColorScheme].
///
/// Holds stock status colors, sync banner backgrounds, and payment method
/// badge backgrounds — all with light and dark variants.
///
/// Usage:
/// ```dart
/// final semantic = Theme.of(context).extension<AppSemanticColors>()!;
/// Container(color: semantic.stockCriticalContainer);
/// ```
class AppSemanticColors extends ThemeExtension<AppSemanticColors> {
  /// Creates [AppSemanticColors].
  const AppSemanticColors({
    required this.stockCritical,
    required this.stockCriticalContainer,
    required this.stockLow,
    required this.stockLowContainer,
    required this.stockOk,
    required this.stockOkContainer,
    required this.syncingContainer,
    required this.pendingContainer,
    required this.syncOkContainer,
    required this.orangeMoneyBg,
    required this.mtnBg,
    required this.waveBg,
  });

  // Stock status — Rupture / Critique
  /// Stock out / critical foreground color.
  final Color stockCritical;

  /// Stock out / critical container background.
  final Color stockCriticalContainer;

  // Stock status — Bas / Réapprovisionnement
  /// Low stock / reorder needed foreground color.
  final Color stockLow;

  /// Low stock / reorder container background.
  final Color stockLowContainer;

  // Stock status — OK / Disponible
  /// Stock available foreground color.
  final Color stockOk;

  /// Stock available container background.
  final Color stockOkContainer;

  // Sync banner backgrounds
  /// Background for "sync in progress" banner.
  final Color syncingContainer;

  /// Background for "pending sync" banner.
  final Color pendingContainer;

  /// Background for "sync up to date" banner.
  final Color syncOkContainer;

  // Payment method badge backgrounds
  /// Orange Money badge background.
  final Color orangeMoneyBg;

  /// MTN Mobile Money badge background.
  final Color mtnBg;

  /// Wave badge background.
  final Color waveBg;

  /// Light mode instance.
  static const light = AppSemanticColors(
    stockCritical: Color(0xFFDC2626),
    stockCriticalContainer: Color(0xFFFEE2E2),
    stockLow: Color(0xFFD97706),
    stockLowContainer: Color(0xFFFEF3C7),
    stockOk: Color(0xFF16A34A),
    stockOkContainer: Color(0xFFDCFCE7),
    syncingContainer: Color(0xFFDBEAFE),
    pendingContainer: Color(0xFFFEF3C7),
    syncOkContainer: Color(0xFFDCFCE7),
    orangeMoneyBg: Color(0xFFFFF4ED),
    mtnBg: Color(0xFFFFFBEB),
    waveBg: Color(0xFFEFF6FF),
  );

  /// Dark mode instance.
  static const dark = AppSemanticColors(
    stockCritical: Color(0xFFEF4444),
    stockCriticalContainer: Color(0xFF450A0A),
    stockLow: Color(0xFFF59E0B),
    stockLowContainer: Color(0xFF422006),
    stockOk: Color(0xFF10B981),
    stockOkContainer: Color(0xFF022C22),
    syncingContainer: Color(0xFF0C2340),
    pendingContainer: Color(0xFF422006),
    syncOkContainer: Color(0xFF022C22),
    orangeMoneyBg: Color(0xFF3D1A08),
    mtnBg: Color(0xFF362508),
    waveBg: Color(0xFF071830),
  );

  @override
  AppSemanticColors copyWith({
    Color? stockCritical,
    Color? stockCriticalContainer,
    Color? stockLow,
    Color? stockLowContainer,
    Color? stockOk,
    Color? stockOkContainer,
    Color? syncingContainer,
    Color? pendingContainer,
    Color? syncOkContainer,
    Color? orangeMoneyBg,
    Color? mtnBg,
    Color? waveBg,
  }) {
    return AppSemanticColors(
      stockCritical: stockCritical ?? this.stockCritical,
      stockCriticalContainer:
          stockCriticalContainer ?? this.stockCriticalContainer,
      stockLow: stockLow ?? this.stockLow,
      stockLowContainer: stockLowContainer ?? this.stockLowContainer,
      stockOk: stockOk ?? this.stockOk,
      stockOkContainer: stockOkContainer ?? this.stockOkContainer,
      syncingContainer: syncingContainer ?? this.syncingContainer,
      pendingContainer: pendingContainer ?? this.pendingContainer,
      syncOkContainer: syncOkContainer ?? this.syncOkContainer,
      orangeMoneyBg: orangeMoneyBg ?? this.orangeMoneyBg,
      mtnBg: mtnBg ?? this.mtnBg,
      waveBg: waveBg ?? this.waveBg,
    );
  }

  @override
  AppSemanticColors lerp(ThemeExtension<AppSemanticColors>? other, double t) {
    if (other is! AppSemanticColors) return this;
    return AppSemanticColors(
      stockCritical: Color.lerp(stockCritical, other.stockCritical, t)!,
      stockCriticalContainer: Color.lerp(
        stockCriticalContainer,
        other.stockCriticalContainer,
        t,
      )!,
      stockLow: Color.lerp(stockLow, other.stockLow, t)!,
      stockLowContainer: Color.lerp(
        stockLowContainer,
        other.stockLowContainer,
        t,
      )!,
      stockOk: Color.lerp(stockOk, other.stockOk, t)!,
      stockOkContainer: Color.lerp(
        stockOkContainer,
        other.stockOkContainer,
        t,
      )!,
      syncingContainer: Color.lerp(
        syncingContainer,
        other.syncingContainer,
        t,
      )!,
      pendingContainer: Color.lerp(
        pendingContainer,
        other.pendingContainer,
        t,
      )!,
      syncOkContainer: Color.lerp(syncOkContainer, other.syncOkContainer, t)!,
      orangeMoneyBg: Color.lerp(orangeMoneyBg, other.orangeMoneyBg, t)!,
      mtnBg: Color.lerp(mtnBg, other.mtnBg, t)!,
      waveBg: Color.lerp(waveBg, other.waveBg, t)!,
    );
  }
}
