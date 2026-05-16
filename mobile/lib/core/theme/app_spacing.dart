/// Spacing and layout tokens for POS Mobile CI.
///
/// All spacing values follow an 8pt base grid for consistency and rhythm.
/// Border radii follow a similar progression for visual coherence.
/// Tap target sizes meet or exceed WCAG accessibility standards (44dp minimum)
/// and accommodate users with limited dexterity or large fingers.
class AppSpacing {
  /// Prevent instantiation
  AppSpacing._();

  // Spacing tokens (base 8pt grid)
  /// Extra small spacing. 4pt — use for micro-padding within components.
  static const double xs = 4;

  /// Small spacing. 8pt — standard padding for small elements, tight spacing.
  static const double sm = 8;

  /// Medium spacing. 16pt — standard padding for cards, inputs, sections.
  static const double md = 16;

  /// Large spacing. 24pt — padding for major sections and vertical rhythm.
  static const double lg = 24;

  /// Extra large spacing. 32pt — generous spacing for visual breathing room.
  static const double xl = 32;

  /// Double extra large spacing. 48pt — spacing between major layout blocks.
  static const double xxl = 48;

  /// Triple extra large spacing. 64pt — very generous vertical space for onboarding/empty states.
  static const double xxxl = 64;

  // Border radii tokens
  /// Small corner radius. 8pt — chips, small buttons, dialog corners.
  static const double radiusSm = 8;

  /// Medium corner radius. 12pt — inputs, standard buttons, moderate prominence.
  static const double radiusMd = 12;

  /// Large corner radius. 16pt — cards, bottom sheets, elevated surfaces.
  static const double radiusLg = 16;

  /// Extra large corner radius. 24pt — large cards, prominent modals.
  static const double radiusXl = 24;

  /// Fully rounded. 999pt — chips, badges, circular elements, full border radius.
  static const double radiusFull = 999;

  // Tap target / Touch-friendly sizing
  /// Button height — gros doigts, quick one-hand usage. Generous vertical padding.
  /// Usage: ElevatedButton, OutlinedButton, primary and secondary CTA buttons.
  static const double buttonHeight = 56;

  /// Secondary button height — slightly smaller than primary, still easily tappable.
  /// Usage: tertiary buttons, back buttons, cancel actions.
  static const double buttonHeightSm = 48;

  /// Input field height — same as primary button for visual consistency
  /// and to accommodate larger finger taps.
  /// Usage: TextField, TextFormField, search inputs, dropdown fields.
  static const double inputHeight = 56;

  /// Icon button size — minimum 48pt for touch targets, may expand for larger icons.
  /// Usage: IconButton, floating action buttons, inline actions.
  static const double iconButtonSize = 48;

  /// Minimum tap target size per WCAG guidelines (44pt).
  /// Most interactive elements should be at least this size; larger is better.
  static const double minTapTarget = 44;

  // Padding/margin presets
  /// Symmetrical padding for standard containers.
  /// Usage: edgeInsets for cards, dialogs, padding around content.
  static const double contentPadding = md; // 16pt
}
