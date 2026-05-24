import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/theme/app_animations.dart';
import '../../core/theme/app_colors.dart';

/// Animated loading spinner with morphing size/opacity effect.
///
/// Premium alternative to standard CircularProgressIndicator.
/// Scales up/down repeatedly for emphasis while rotating.
class AnimatedLoadingSpinner extends StatefulWidget {
  /// Creates an animated loading spinner.
  const AnimatedLoadingSpinner({
    this.size = 48,
    this.color = AppColors.primary,
    super.key,
  });

  /// Spinner size (diameter).
  final double size;

  /// Spinner color.
  final Color color;

  @override
  State<AnimatedLoadingSpinner> createState() => _AnimatedLoadingSpinnerState();
}

class _AnimatedLoadingSpinnerState extends State<AnimatedLoadingSpinner>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _scaleAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: AppAnimations.slow,
      vsync: this,
    );
    unawaited(_controller.repeat(reverse: true));

    _scaleAnimation = Tween<double>(begin: 0.8, end: 1.2).animate(
      CurvedAnimation(parent: _controller, curve: AppAnimations.easeInOut),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: _scaleAnimation,
      child: SizedBox.square(
        dimension: widget.size,
        child: CircularProgressIndicator(
          strokeWidth: 3,
          valueColor: AlwaysStoppedAnimation<Color>(widget.color),
        ),
      ),
    );
  }
}
