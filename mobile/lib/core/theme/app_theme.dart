import 'package:flutter/material.dart';
import 'app_semantic_colors.dart';
import 'app_spacing.dart';
import 'app_typography.dart';

/// Material 3 theme factory for POS Mobile CI.
///
/// Two public methods: [light] and [dark].
/// Both register [AppSemanticColors] as a [ThemeExtension] for stock status,
/// sync banner, and payment badge colors.
class AppTheme {
  /// Prevent instantiation.
  AppTheme._();

  /// Builds complete Material 3 light theme.
  static ThemeData light() {
    const colorScheme = ColorScheme(
      brightness: Brightness.light,
      primary: Color(0xFF2563EB),
      onPrimary: Color(0xFFFFFFFF),
      primaryContainer: Color(0xFFDBEAFE),
      onPrimaryContainer: Color(0xFF1D4ED8),
      secondary: Color(0xFF16A34A),
      onSecondary: Color(0xFFFFFFFF),
      secondaryContainer: Color(0xFFDCFCE7),
      onSecondaryContainer: Color(0xFF15803D),
      tertiary: Color(0xFFD97706), // amber — warning / offline banner
      onTertiary: Color(0xFFFFFFFF),
      tertiaryContainer: Color(0xFFFEF3C7),
      onTertiaryContainer: Color(0xFF92400E),
      error: Color(0xFFDC2626),
      onError: Color(0xFFFFFFFF),
      errorContainer: Color(0xFFFEE2E2),
      onErrorContainer: Color(0xFFDC2626),
      surface: Color(0xFFFFFFFF),
      onSurface: Color(0xFF0F172A),
      surfaceContainerHighest: Color(0xFFF1F5F9),
      onSurfaceVariant: Color(0xFF475569),
      outline: Color(0xFFE2E8F0),
      outlineVariant: Color(0xFFF1F5F9),
      scrim: Color(0x990F172A),
      shadow: Color(0xFF000000),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFFF8FAFC),
      extensions: const [AppSemanticColors.light],
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
      primary: Color(0xFF38BDF8), // electric sky blue
      onPrimary: Color(0xFF082F49),
      primaryContainer: Color(0xFF0C4A6E),
      onPrimaryContainer: Color(0xFFE0F2FE),
      secondary: Color(0xFF10B981), // emerald green
      onSecondary: Color(0xFF022C22),
      secondaryContainer: Color(0xFF022C22),
      onSecondaryContainer: Color(0xFFD1FAE5),
      tertiary: Color(0xFFF59E0B), // amber warning
      onTertiary: Color(0xFF422006),
      tertiaryContainer: Color(0xFF422006),
      onTertiaryContainer: Color(0xFFFEF3C7),
      error: Color(0xFFEF4444),
      onError: Color(0xFF450A0A),
      errorContainer: Color(0xFF450A0A),
      onErrorContainer: Color(0xFFFEE2E2),
      surface: Color(0xFF1E293B), // dark slate card surface
      onSurface: Color(0xFFF8FAFC), // near-white text
      surfaceContainerHighest: Color(0xFF334155),
      onSurfaceVariant: Color(0xFF94A3B8), // secondary text
      outline: Color(0xFF475569),
      outlineVariant: Color(0xFF334155),
      scrim: Color(0x990B0F19),
      shadow: Color(0xFF000000),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFF0B0F19), // near-black blue
      extensions: const [AppSemanticColors.dark],
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
