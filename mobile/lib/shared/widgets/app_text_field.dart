import 'package:flutter/material.dart';

import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';

/// Accessible text input field with persistent label.
///
/// Label is always visible above the input to avoid confusion for
/// low-literacy users. Thick borders and large touch area (56dp minimum).
class AppTextField extends StatefulWidget {
  /// Creates an app text field.
  const AppTextField({
    required this.label,
    this.hint,
    this.controller,
    this.keyboardType = TextInputType.text,
    this.obscureText = false,
    this.errorText,
    this.prefixIcon,
    this.suffixIcon,
    this.onChanged,
    this.maxLines = 1,
    this.minLines,
    super.key,
  });

  /// Label text displayed above the field (always visible).
  final String label;

  /// Hint text displayed inside the field when empty.
  final String? hint;

  /// Text editing controller.
  final TextEditingController? controller;

  /// Keyboard type for the input.
  final TextInputType keyboardType;

  /// Whether to hide the text (for passwords).
  final bool obscureText;

  /// Error message to display below the field. If null, no error state.
  final String? errorText;

  /// Icon displayed at the start of the input.
  final IconData? prefixIcon;

  /// Icon displayed at the end of the input.
  final IconData? suffixIcon;

  /// Callback when text changes.
  final ValueChanged<String>? onChanged;

  /// Number of lines (default 1 for single-line input).
  final int maxLines;

  /// Minimum number of lines for multi-line input.
  final int? minLines;

  @override
  State<AppTextField> createState() => _AppTextFieldState();
}

class _AppTextFieldState extends State<AppTextField> {
  late FocusNode _focusNode;
  late bool _isObscured;

  @override
  void initState() {
    super.initState();
    _focusNode = FocusNode();
    _focusNode.addListener(() {
      setState(() {});
    });
    _isObscured = widget.obscureText;
  }

  @override
  void dispose() {
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final hasError = widget.errorText != null && widget.errorText!.isNotEmpty;
    final borderColor = hasError ? AppColors.error : AppColors.border;
    final activeBorderColor = hasError ? AppColors.error : AppColors.primary;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(widget.label, style: AppTypography.labelMedium),
        const SizedBox(height: AppSpacing.xs),
        SizedBox(
          height: widget.maxLines == 1 ? 56 : null,
          child: TextField(
            controller: widget.controller,
            focusNode: _focusNode,
            obscureText: _isObscured,
            keyboardType: widget.keyboardType,
            maxLines: widget.maxLines,
            minLines: widget.minLines,
            onChanged: widget.onChanged,
            style: AppTypography.bodyMedium,
            decoration: InputDecoration(
              hintText: widget.hint,
              hintStyle: AppTypography.hintText,
              prefixIcon: widget.prefixIcon != null
                  ? Icon(widget.prefixIcon, color: AppColors.textSecondary)
                  : null,
              suffixIcon: widget.obscureText
                  ? IconButton(
                      icon: Icon(
                        _isObscured
                            ? Icons.visibility_off_outlined
                            : Icons.visibility_outlined,
                        color: AppColors.textSecondary,
                      ),
                      onPressed: () =>
                          setState(() => _isObscured = !_isObscured),
                    )
                  : (widget.suffixIcon != null
                        ? Icon(
                            widget.suffixIcon,
                            color: AppColors.textSecondary,
                          )
                        : null),
              filled: true,
              fillColor: AppColors.surface,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                borderSide: BorderSide(color: borderColor, width: 2),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                borderSide: BorderSide(color: borderColor, width: 2),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                borderSide: BorderSide(color: activeBorderColor, width: 2),
              ),
              errorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                borderSide: const BorderSide(color: AppColors.error, width: 2),
              ),
              focusedErrorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                borderSide: const BorderSide(color: AppColors.error, width: 2),
              ),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm,
              ),
            ),
          ),
        ),
        if (hasError) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(widget.errorText!, style: AppTypography.errorText),
        ],
      ],
    );
  }
}
