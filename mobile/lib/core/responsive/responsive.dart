import 'package:flutter/material.dart';

/// Responsive design helpers for adapting UI across different screen sizes.
///
/// The POS app targets a wide range of Android devices (4.5" to 6.7" screens).
/// These helpers enable single-codebase layouts that scale appropriately from
/// small budget phones to larger screens without needing completely different UIs.
extension ResponsiveContext on BuildContext {
  /// Screen width in logical pixels.
  double get screenWidth => MediaQuery.of(this).size.width;

  /// Screen height in logical pixels.
  double get screenHeight => MediaQuery.of(this).size.height;

  /// Device padding (safe area insets) — sum of all sides.
  EdgeInsets get devicePadding => MediaQuery.of(this).padding;

  /// True if screen width < 360dp. Small budget phones (4.5"–5.0").
  bool get isSmallScreen => screenWidth < 360;

  /// True if screen width ≥ 360dp and < 600dp. Medium phones (5.0"–6.0").
  bool get isMediumScreen => screenWidth >= 360 && screenWidth < 600;

  /// True if screen width ≥ 600dp. Large phones and tablets (6.0"+).
  bool get isLargeScreen => screenWidth >= 600;

  /// Orientation: true if landscape (width > height).
  bool get isLandscape => screenWidth > screenHeight;

  /// Orientation: true if portrait (height > width).
  bool get isPortrait => screenHeight > screenWidth;

  /// Device pixel ratio (logical pixels → physical pixels).
  /// Helps detect retina/high-DPI screens.
  double get devicePixelRatio => MediaQuery.of(this).devicePixelRatio;

  /// Remaining height after removing status and navigation bars (safe area).
  /// Useful for calculating remaining space in layouts.
  double get availableHeight {
    final padding = MediaQuery.of(this).padding;
    return screenHeight - padding.top - padding.bottom;
  }
}

/// Pick a value based on screen size classification.
///
/// Enables fluid responsive design without media queries. Returns the most
/// appropriate value for the current screen size.
///
/// Example:
/// ```dart
/// final padding = responsiveValue<double>(
///   context,
///   small: 8,
///   medium: 16,
///   large: 24,
/// );
/// ```
T responsiveValue<T>(
  BuildContext context, {
  required T small,
  required T medium,
  T? large,
}) {
  if (context.isLargeScreen && large != null) {
    return large;
  }
  if (context.isSmallScreen) {
    return small;
  }
  return medium;
}

/// Pick a layout mode based on screen size.
///
/// Simplifies choosing between single-column (mobile) and multi-column
/// (tablet) layouts. Returns `LayoutMode.compact` for small screens,
/// `LayoutMode.expanded` for medium/large.
///
/// Example:
/// ```dart
/// final layout = responsiveLayout(context);
/// if (layout == LayoutMode.compact) {
///   return SingleChildScrollView(...);
/// } else {
///   return Row(...);
/// }
/// ```
LayoutMode responsiveLayout(BuildContext context) {
  return context.isSmallScreen ? LayoutMode.compact : LayoutMode.expanded;
}

/// Layout classification for responsive design decisions.
enum LayoutMode {
  /// Single-column vertical layout (mobile phones). Width < 360dp.
  compact,

  /// Multi-column or wider layout (tablets or large phones). Width ≥ 360dp.
  expanded,
}

/// Breakpoint constants for manual media queries (if needed).
abstract class ResponsiveBreakpoints {
  /// Small screen threshold: 360dp. Includes most budget Android phones.
  static const double small = 360;

  /// Medium screen threshold: 600dp. Includes most tablets.
  static const double medium = 600;

  /// Large screen threshold: 900dp. Large tablets and foldables.
  static const double large = 900;
}
