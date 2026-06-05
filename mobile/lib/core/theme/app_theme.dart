import 'package:flutter/material.dart';
import 'app_spacing.dart';
import 'app_typography.dart';

/// Material 3 theme factory for POS Mobile CI.
///
/// Two public methods: [light] and [dark].
class AppTheme {
  /// Prevent instantiation.
  AppTheme._();

  /// Builds complete Material 3 light theme.
  static ThemeData light() {
    const colorScheme = ColorScheme(
      brightness: Brightness.light,
      primary: Color(0xFF92400E), // brun cacao — WCAG 7.1:1 on white
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: Color(0xFFFEF3C7), // amber-100
      onPrimaryContainer: Color(0xFF451A03), // brown-950
      secondary: Color(0xFFCA8A04), // or/doré — ≠ jaune MTN #FFCC00
      onSecondary: Color(0xFF1C1107), // jamais blanc sur or (3.4:1 insuffisant)
      secondaryContainer: Color(0xFFFEFCE8), // yellow-50
      onSecondaryContainer: Color(0xFF713F12), // amber-800
      tertiary: Color(0xFFC2410C), // orange-rouge — warning/offline banner
      onTertiary: Color(0xFFFFFFFF),
      tertiaryContainer: Color(0xFFFFEDD5), // orange-100
      onTertiaryContainer: Color(0xFF7C2D12), // orange-950
      error: Color(0xFFBA1A1A),
      onError: Color(0xFFFFFFFF),
      errorContainer: Color(0xFFFFDAD6),
      onErrorContainer: Color(0xFF410002),
      surface: Color(0xFFFFFFFF),
      onSurface: Color(0xFF1C1107), // warm near-black
      surfaceContainerHighest: Color(0xFFFEF9EE), // ivory-warm tint
      onSurfaceVariant: Color(0xFF57534E), // stone-600
      outline: Color(0xFFA8A29E), // stone-400
      outlineVariant: Color(0xFFE7E5E4), // stone-200
      scrim: Color(0x991C1107),
      shadow: Color(0xFF000000),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFFFFFBF5), // ivory-warm
      textTheme: _buildTextTheme(colorScheme),
      appBarTheme: _buildAppBarTheme(colorScheme),
      cardTheme: _buildCardTheme(colorScheme),
      inputDecorationTheme: _buildInputDecorationTheme(colorScheme),
      elevatedButtonTheme: _buildElevatedButtonTheme(colorScheme),
      outlinedButtonTheme: _buildOutlinedButtonTheme(colorScheme),
      textButtonTheme: _buildTextButtonTheme(colorScheme),
      chipTheme: _buildChipTheme(colorScheme),
      dividerTheme: _buildDividerTheme(colorScheme),
      snackBarTheme: _buildSnackBarTheme(colorScheme),
      bottomNavigationBarTheme: _buildBottomNavTheme(colorScheme),
      floatingActionButtonTheme: _buildFabTheme(colorScheme),
      progressIndicatorTheme: _buildProgressIndicatorTheme(colorScheme),
      switchTheme: _buildSwitchTheme(colorScheme),
      checkboxTheme: _buildCheckboxTheme(colorScheme),
    );
  }

  /// Builds complete Material 3 dark theme.
  static ThemeData dark() {
    const colorScheme = ColorScheme(
      brightness: Brightness.dark,
      primary: Color(0xFFFDBA74), // amber-300 — cacao clair sur fond sombre
      onPrimary: Color(0xFF431407), // very dark cacao
      primaryContainer: Color(0xFF78350F), // amber-900
      onPrimaryContainer: Color(0xFFFEF3C7), // amber-100
      secondary: Color(0xFFFDE68A), // amber-200 — or clair sur fond sombre
      onSecondary: Color(0xFF451A03), // très sombre
      secondaryContainer: Color(0xFF713F12), // amber-800
      onSecondaryContainer: Color(0xFFFEFCE8), // yellow-50
      tertiary: Color(
        0xFFFB923C,
      ), // orange-400 — warning/offline sur fond sombre
      onTertiary: Color(0xFF431407),
      tertiaryContainer: Color(0xFF7C2D12), // orange-950
      onTertiaryContainer: Color(0xFFFFEDD5), // orange-100
      error: Color(0xFFFFB4AB),
      onError: Color(0xFF690005),
      errorContainer: Color(0xFF93000A),
      onErrorContainer: Color(0xFFFFDAD6),
      surface: Color(0xFF1C1107), // near-black warm brown
      onSurface: Color(0xFFF5F0E8), // warm white
      surfaceContainerHighest: Color(0xFF3D2A14), // dark warm brown
      onSurfaceVariant: Color(0xFFD6C7B8), // warm light gray
      outline: Color(0xFF9D8E81),
      outlineVariant: Color(0xFF4A3728),
      scrim: Color(0x990C0906),
      shadow: Color(0xFF000000),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFF0C0906), // near-black warm cacao
      textTheme: _buildTextTheme(colorScheme),
      appBarTheme: _buildAppBarTheme(colorScheme),
      cardTheme: _buildCardTheme(colorScheme),
      inputDecorationTheme: _buildInputDecorationTheme(colorScheme),
      elevatedButtonTheme: _buildElevatedButtonTheme(colorScheme),
      outlinedButtonTheme: _buildOutlinedButtonTheme(colorScheme),
      textButtonTheme: _buildTextButtonTheme(colorScheme),
      chipTheme: _buildChipTheme(colorScheme),
      dividerTheme: _buildDividerTheme(colorScheme),
      snackBarTheme: _buildSnackBarTheme(colorScheme),
      bottomNavigationBarTheme: _buildBottomNavTheme(colorScheme),
      floatingActionButtonTheme: _buildFabTheme(colorScheme),
      progressIndicatorTheme: _buildProgressIndicatorTheme(colorScheme),
      switchTheme: _buildSwitchTheme(colorScheme),
      checkboxTheme: _buildCheckboxTheme(colorScheme),
    );
  }

  static TextTheme _buildTextTheme(ColorScheme cs) {
    final primary = cs.onSurface;
    final secondary = cs.onSurfaceVariant;
    return TextTheme(
      displayLarge: AppTypography.displayLarge.copyWith(color: primary),
      displayMedium: AppTypography.displayMedium.copyWith(color: primary),
      headlineLarge: AppTypography.titleLarge.copyWith(color: primary),
      headlineMedium: AppTypography.titleMedium.copyWith(color: primary),
      titleLarge: AppTypography.titleLarge.copyWith(color: primary),
      titleMedium: AppTypography.titleMedium.copyWith(color: primary),
      bodyLarge: AppTypography.bodyLarge.copyWith(color: primary),
      bodyMedium: AppTypography.bodyMedium.copyWith(color: primary),
      bodySmall: AppTypography.bodySmall.copyWith(color: secondary),
      labelLarge: AppTypography.labelLarge.copyWith(color: primary),
      labelMedium: AppTypography.labelMedium.copyWith(color: primary),
      labelSmall: AppTypography.labelSmall.copyWith(color: secondary),
    );
  }

  static AppBarTheme _buildAppBarTheme(ColorScheme cs) {
    return AppBarTheme(
      backgroundColor: cs.surface,
      foregroundColor: cs.onSurface,
      elevation: 0,
      scrolledUnderElevation: 1,
      titleTextStyle: AppTypography.titleLarge.copyWith(color: cs.onSurface),
      toolbarTextStyle: AppTypography.bodyMedium.copyWith(color: cs.onSurface),
      centerTitle: false,
      iconTheme: IconThemeData(color: cs.onSurface),
    );
  }

  static CardThemeData _buildCardTheme(ColorScheme cs) {
    return CardThemeData(
      color: cs.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
      ),
    );
  }

  static InputDecorationTheme _buildInputDecorationTheme(ColorScheme cs) {
    final fillColor = cs.surfaceContainer;
    return InputDecorationTheme(
      filled: true,
      fillColor: fillColor,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: 18,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        borderSide: BorderSide(color: cs.outline),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        borderSide: BorderSide(color: cs.outline),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        borderSide: BorderSide(color: cs.primary, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        borderSide: BorderSide(color: cs.error),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        borderSide: BorderSide(color: cs.error, width: 2),
      ),
      disabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        borderSide: BorderSide(color: cs.outlineVariant),
      ),
      labelStyle: AppTypography.labelMedium.copyWith(
        color: cs.onSurfaceVariant,
      ),
      hintStyle: AppTypography.hintText.copyWith(color: cs.onSurfaceVariant),
      helperStyle: AppTypography.captionText.copyWith(
        color: cs.onSurfaceVariant,
      ),
      errorStyle: AppTypography.errorText.copyWith(color: cs.error),
    );
  }

  static ElevatedButtonThemeData _buildElevatedButtonTheme(ColorScheme cs) {
    return ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: cs.primary,
        foregroundColor: cs.onPrimary,
        minimumSize: const Size(double.infinity, AppSpacing.buttonHeight),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: 12,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        ),
        textStyle: AppTypography.labelLarge,
        elevation: 0,
      ),
    );
  }

  static OutlinedButtonThemeData _buildOutlinedButtonTheme(ColorScheme cs) {
    return OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: cs.primary,
        minimumSize: const Size(double.infinity, AppSpacing.buttonHeight),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: 12,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        ),
        side: BorderSide(color: cs.primary, width: 2),
        textStyle: AppTypography.labelLarge,
      ),
    );
  }

  static TextButtonThemeData _buildTextButtonTheme(ColorScheme cs) {
    return TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: cs.primary,
        textStyle: AppTypography.labelLarge,
      ),
    );
  }

  static ChipThemeData _buildChipTheme(ColorScheme cs) {
    return ChipThemeData(
      backgroundColor: cs.surfaceContainer,
      selectedColor: cs.primaryContainer,
      deleteIconColor: cs.onSurfaceVariant,
      disabledColor: cs.outlineVariant,
      labelStyle: AppTypography.labelMedium.copyWith(color: cs.onSurface),
      secondaryLabelStyle: AppTypography.labelMedium.copyWith(
        color: cs.onSurface,
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.xs,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
        side: BorderSide(color: cs.outline),
      ),
    );
  }

  static DividerThemeData _buildDividerTheme(ColorScheme cs) {
    return DividerThemeData(
      color: cs.outlineVariant,
      thickness: 1,
      space: AppSpacing.md,
    );
  }

  static SnackBarThemeData _buildSnackBarTheme(ColorScheme cs) {
    return SnackBarThemeData(
      backgroundColor: cs.onSurface,
      contentTextStyle: AppTypography.bodyMedium.copyWith(color: cs.surface),
      actionTextColor: cs.primary,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      ),
    );
  }

  static BottomNavigationBarThemeData _buildBottomNavTheme(ColorScheme cs) {
    return BottomNavigationBarThemeData(
      backgroundColor: cs.surface,
      selectedItemColor: cs.primary,
      unselectedItemColor: cs.onSurfaceVariant,
      selectedLabelStyle: AppTypography.labelMedium,
      unselectedLabelStyle: AppTypography.labelMedium,
      type: BottomNavigationBarType.fixed,
      elevation: 0,
    );
  }

  static FloatingActionButtonThemeData _buildFabTheme(ColorScheme cs) {
    return FloatingActionButtonThemeData(
      backgroundColor: cs.primary,
      foregroundColor: cs.onPrimary,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpacing.radiusSm),
      ),
    );
  }

  static ProgressIndicatorThemeData _buildProgressIndicatorTheme(
    ColorScheme cs,
  ) {
    final track = cs.surfaceContainer;
    return ProgressIndicatorThemeData(
      color: cs.primary,
      linearTrackColor: track,
      circularTrackColor: track,
    );
  }

  static SwitchThemeData _buildSwitchTheme(ColorScheme cs) {
    return SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return cs.onPrimary;
        return cs.outline;
      }),
      trackColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return cs.primary;
        return cs.surfaceContainer;
      }),
    );
  }

  static CheckboxThemeData _buildCheckboxTheme(ColorScheme cs) {
    return CheckboxThemeData(
      fillColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return cs.primary;
        return cs.surface;
      }),
      side: BorderSide(color: cs.outline, width: 2),
    );
  }
}
