/// SVG illustrations for empty states and feedback.
///
/// Minimalist style, terracotta + emerald palette.
/// Use with flutter_svg.SvgPicture.string().
abstract class Illustrations {
  /// Prevent instantiation
  Illustrations._();

  /// Empty catalog (no products).
  static const String emptyCatalog = '''
<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <rect x="40" y="60" width="120" height="80" rx="8" fill="none" stroke="#C1583A" stroke-width="3"/>
  <path d="M 60 80 L 80 100 L 100 85 L 140 120" fill="none" stroke="#1A7A5E" stroke-width="3" stroke-linecap="round"/>
  <circle cx="75" cy="75" r="4" fill="#1A7A5E"/>
</svg>
  ''';

  /// Empty sales (no sales yet).
  static const String emptySales = '''
<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <path d="M 50 120 L 100 60 L 150 100 L 160 85" fill="none" stroke="#C1583A" stroke-width="3" stroke-linecap="round"/>
  <circle cx="100" cy="60" r="5" fill="#1A7A5E"/>
  <line x1="40" y1="140" x2="160" y2="140" stroke="#D9D0C9" stroke-width="2"/>
</svg>
  ''';

  /// Error state (something went wrong).
  static const String errorState = '''
<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <circle cx="100" cy="100" r="60" fill="none" stroke="#C0392B" stroke-width="3"/>
  <line x1="75" y1="75" x2="125" y2="125" stroke="#C0392B" stroke-width="4" stroke-linecap="round"/>
  <line x1="125" y1="75" x2="75" y2="125" stroke="#C0392B" stroke-width="4" stroke-linecap="round"/>
</svg>
  ''';

  /// Success state (transaction complete).
  static const String successState = '''
<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <circle cx="100" cy="100" r="60" fill="none" stroke="#1A7A5E" stroke-width="3"/>
  <path d="M 80 100 L 95 115 L 125 80" fill="none" stroke="#1A7A5E" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
  ''';

  /// Loading state (processing).
  static const String loadingState = '''
<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <circle cx="100" cy="100" r="50" fill="none" stroke="#E07B5F" stroke-width="3" stroke-dasharray="31.4 62.8"/>
</svg>
  ''';

  /// No network (offline).
  static const String noNetwork = '''
<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <path d="M 60 120 Q 100 80 140 120" fill="none" stroke="#C1583A" stroke-width="3" stroke-linecap="round"/>
  <circle cx="100" cy="135" r="4" fill="#C1583A"/>
  <line x1="45" y1="160" x2="155" y2="160" stroke="#D9D0C9" stroke-width="2"/>
  <circle cx="70" cy="150" r="3" fill="#D9D0C9"/>
  <circle cx="100" cy="150" r="3" fill="#D9D0C9"/>
  <circle cx="130" cy="150" r="3" fill="#D9D0C9"/>
</svg>
  ''';

  /// Empty cart (add items to cart).
  static const String emptyCart = '''
<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
  <path d="M 50 60 L 60 140 Q 60 150 70 150 L 130 150 Q 140 150 140 140 L 150 60 Z" fill="none" stroke="#C1583A" stroke-width="3" stroke-linejoin="round"/>
  <line x1="48" y1="60" x2="152" y2="60" stroke="#C1583A" stroke-width="3"/>
  <line x1="80" y1="60" x2="80" y2="50" stroke="#1A7A5E" stroke-width="2" stroke-linecap="round"/>
  <line x1="120" y1="60" x2="120" y2="50" stroke="#1A7A5E" stroke-width="2" stroke-linecap="round"/>
</svg>
  ''';
}
