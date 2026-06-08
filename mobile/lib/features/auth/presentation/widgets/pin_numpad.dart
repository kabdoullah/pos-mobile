import 'package:flutter/material.dart';

import '../../../../core/theme/app_spacing.dart';

/// 4-dot PIN progress indicator.
///
/// Each dot fills (primary color) as digits are entered.
class PinDots extends StatelessWidget {
  /// Creates a PIN dots indicator.
  const PinDots({super.key, required this.filledCount, this.length = 4});

  /// Number of filled dots (digits entered).
  final int filledCount;

  /// Total number of dots (PIN length).
  final int length;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(length, (i) {
        final filled = i < filledCount;
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            width: 16,
            height: 16,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: filled ? cs.primary : Colors.transparent,
              border: Border.all(
                color: filled ? cs.primary : cs.outline,
                width: 2,
              ),
            ),
          ),
        );
      }),
    );
  }
}

/// Custom PIN numpad — 3×4 grid, no system keyboard.
///
/// Layout:
/// ```
/// 1  2  3
/// 4  5  6
/// 7  8  9
/// _  0  ⌫
/// ```
class PinNumpad extends StatelessWidget {
  /// Creates a PIN numpad.
  const PinNumpad({
    super.key,
    required this.onDigit,
    required this.onBackspace,
    this.enabled = true,
  });

  /// Called with the digit string when a number key is tapped.
  final void Function(String digit) onDigit;

  /// Called when the backspace key is tapped.
  final VoidCallback onBackspace;

  /// Whether key interaction is enabled (disable during async ops).
  final bool enabled;

  static const List<List<String?>> _layout = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    [null, '0', 'backspace'],
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: _layout.map((row) {
        return Padding(
          padding: const EdgeInsets.only(bottom: AppSpacing.sm),
          child: Row(
            children: row.map((key) {
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.xs,
                  ),
                  child: _buildKey(context, key),
                ),
              );
            }).toList(),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildKey(BuildContext context, String? key) {
    if (key == null) return const SizedBox.shrink();

    final cs = Theme.of(context).colorScheme;

    if (key == 'backspace') {
      return _NumpadKey(
        onTap: enabled ? onBackspace : null,
        child: Icon(Icons.backspace_outlined, color: cs.onSurface, size: 22),
      );
    }

    return _NumpadKey(
      onTap: enabled ? () => onDigit(key) : null,
      child: Text(
        key,
        style: TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.w600,
          color: cs.onSurface,
        ),
      ),
    );
  }
}

class _NumpadKey extends StatelessWidget {
  const _NumpadKey({required this.child, this.onTap});

  final Widget child;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Material(
      color: cs.surface,
      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
      elevation: 1.5,
      shadowColor: cs.shadow,
      child: InkWell(
        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
        onTap: onTap,
        child: SizedBox(height: 64, child: Center(child: child)),
      ),
    );
  }
}
