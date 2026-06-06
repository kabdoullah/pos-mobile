import 'package:flutter/material.dart';

import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';

/// Horizontal step indicator for the 3-step registration flow.
///
/// Shows past steps as filled + check, active step as filled + number,
/// future steps as outlined + muted number.
class RegistrationStepper extends StatelessWidget {
  /// Creates a registration stepper.
  const RegistrationStepper({required this.currentStep, super.key});

  /// Current step index (1-based). Must be between 1 and [_labels.length].
  final int currentStep;

  static const List<String> _labels = ['Compte', 'Boutique', 'Sécurité'];

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final totalSteps = _labels.length;

    // ✨ [A11y] Annonce la progression à VoiceOver/TalkBack avec un label consolidé.
    //    excludeSemantics=true évite que les cercles enfants soient lus individuellement.
    return Semantics(
      label: 'Étape $currentStep sur $totalSteps : ${_labels[currentStep - 1]}',
      excludeSemantics: true,
      child: Row(
        children: [
          for (int i = 0; i < totalSteps; i++) ...[
            _StepCircle(
              index: i + 1,
              currentStep: currentStep,
              label: _labels[i],
            ),
            if (i < totalSteps - 1)
              Expanded(
                // ✨ [UX] AnimatedContainer → transition fluide quand currentStep change.
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeInOut,
                  height: 2,
                  color: (i + 1) < currentStep
                      ? cs.primary
                      : cs.outlineVariant,
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _StepCircle extends StatelessWidget {
  const _StepCircle({
    required this.index,
    required this.currentStep,
    required this.label,
  });

  final int index;
  final int currentStep;
  final String label;

  // ✨ [Qualité] Constante locale — évite le passage inutile en paramètre.
  static const double _size = 28;

  @override
  Widget build(BuildContext context) {
    // ✨ [Qualité] Accès direct au contexte — supprime le param colorScheme du parent.
    final cs = Theme.of(context).colorScheme;
    final isPast = index < currentStep;
    final isActive = index == currentStep;
    final isFilled = isPast || isActive;

    final bgColor = isFilled ? cs.primary : Colors.transparent;
    final borderColor = isFilled ? cs.primary : cs.outlineVariant;
    final contentColor = isFilled ? cs.onPrimary : cs.outlineVariant;

    // ✨ [Qualité] isPast et isActive → même couleur, factorisé.
    final labelColor = isFilled ? cs.primary : cs.outlineVariant;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // ✨ [UX] AnimatedContainer → animation fill/border lors du passage à cet étape.
        AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
          width: _size,
          height: _size,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: bgColor,
            border: Border.all(color: borderColor, width: 2),
          ),
          child: Center(
            child: isPast
                ? Icon(Icons.check, size: 14, color: contentColor)
                : Text(
                    '$index',
                    // ✨ [Design system] AppTypography token au lieu de TextStyle inline.
                    style: AppTypography.labelSmall.copyWith(
                      fontWeight: FontWeight.w600,
                      color: contentColor,
                    ),
                  ),
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        // ✨ [UX] AnimatedDefaultTextStyle → transition couleur du label fluide.
        AnimatedDefaultTextStyle(
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
          style: AppTypography.labelSmall.copyWith(
            color: labelColor,
            fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
          ),
          child: Text(label),
        ),
      ],
    );
  }
}
