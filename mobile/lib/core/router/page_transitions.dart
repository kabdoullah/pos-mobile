import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../theme/app_animations.dart';

/// Custom page transition builders for smooth navigation.
///
/// Provides fade, slide, and scale transitions for different route types.
/// Used by GoRouter to create consistent, premium motion.
abstract class PageTransitions {
  /// Fade transition. For modal-like flows (auth pages, settings).
  static CustomTransitionPage<T> fade<T>(
    BuildContext context,
    GoRouterState state,
    Widget child,
  ) {
    return CustomTransitionPage<T>(
      key: state.pageKey,
      child: child,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        return FadeTransition(opacity: animation, child: child);
      },
      transitionDuration: AppAnimations.standard,
      reverseTransitionDuration: AppAnimations.standard,
    );
  }

  /// Slide transition (left to right). For forward navigation.
  static CustomTransitionPage<T> slideRight<T>(
    BuildContext context,
    GoRouterState state,
    Widget child,
  ) {
    return CustomTransitionPage<T>(
      key: state.pageKey,
      child: child,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = Offset(-1.0, 0.0);
        const end = Offset.zero;
        final tween = Tween(begin: begin, end: end);
        final offsetAnimation = animation.drive(tween);
        return SlideTransition(position: offsetAnimation, child: child);
      },
      transitionDuration: AppAnimations.standard,
      reverseTransitionDuration: AppAnimations.standard,
    );
  }

  /// Slide transition (right to left, exit). For back navigation.
  static CustomTransitionPage<T> slideLeft<T>(
    BuildContext context,
    GoRouterState state,
    Widget child,
  ) {
    return CustomTransitionPage<T>(
      key: state.pageKey,
      child: child,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = Offset(1.0, 0.0);
        const end = Offset.zero;
        final tween = Tween(begin: begin, end: end);
        final offsetAnimation = animation.drive(tween);
        return SlideTransition(position: offsetAnimation, child: child);
      },
      transitionDuration: AppAnimations.standard,
      reverseTransitionDuration: AppAnimations.standard,
    );
  }

  /// Scale transition. For detail/modal opens (product detail, sale detail).
  static CustomTransitionPage<T> scale<T>(
    BuildContext context,
    GoRouterState state,
    Widget child,
  ) {
    return CustomTransitionPage<T>(
      key: state.pageKey,
      child: child,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const begin = 0.95;
        const end = 1.0;
        final tween = Tween(begin: begin, end: end);
        final scaleAnimation = animation.drive(tween);
        return ScaleTransition(scale: scaleAnimation, child: child);
      },
      transitionDuration: AppAnimations.standard,
      reverseTransitionDuration: AppAnimations.standard,
    );
  }

  /// Fade + scale transition. Premium feel for important modals.
  static CustomTransitionPage<T> fadeScale<T>(
    BuildContext context,
    GoRouterState state,
    Widget child,
  ) {
    return CustomTransitionPage<T>(
      key: state.pageKey,
      child: child,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        const beginScale = 0.9;
        const endScale = 1.0;
        final scaleTween = Tween(begin: beginScale, end: endScale);
        final scaleAnimation = animation.drive(scaleTween);

        return FadeTransition(
          opacity: animation,
          child: ScaleTransition(scale: scaleAnimation, child: child),
        );
      },
      transitionDuration: AppAnimations.moderate,
      reverseTransitionDuration: AppAnimations.standard,
    );
  }
}
