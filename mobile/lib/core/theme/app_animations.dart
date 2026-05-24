import 'package:flutter/material.dart';

/// Animation curves and durations for POS Mobile CI.
///
/// Standardized motion for fluent, premium feel. All animations use
/// Material 3 curves (easeIn, easeOut, easeInOut) with durations tuned
/// for quick feedback (short: 150ms) to moderate waits (long: 600ms).
class AppAnimations {
  /// Prevent instantiation
  AppAnimations._();

  // Duration tokens
  /// Very quick feedback (button ripple, toggle). 150ms.
  static const Duration quick = Duration(milliseconds: 150);

  /// Standard transition (page slide, fade). 300ms.
  static const Duration standard = Duration(milliseconds: 300);

  /// Moderate animation (bottom sheet, modal). 400ms.
  static const Duration moderate = Duration(milliseconds: 400);

  /// Slow for emphasis (loading spinner, list cascade). 600ms.
  static const Duration slow = Duration(milliseconds: 600);

  // Curve tokens (Material 3)
  /// Decelerate curve. Use for enter/appear animations.
  static const Curve easeOut = Curves.easeOutCubic;

  /// Accelerate curve. Use for exit/disappear animations.
  static const Curve easeIn = Curves.easeInCubic;

  /// Symmetric curve. Use for bidirectional (toggle, focus).
  static const Curve easeInOut = Curves.easeInOutCubic;

  /// Bouncy curve for playful feedback (rare, optional).
  static const Curve bounce = Curves.elasticOut;
}
