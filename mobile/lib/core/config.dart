/// Configuration globale de l'application.
class AppConfig {
  AppConfig._();

  /// URL de l'API, injectée via --dart-define au build.
  /// En dev sur émulateur Android : http://10.0.2.2:8000
  /// En prod : https://api.pos-mobile-ci.com
  static const String apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'http://192.168.112.252:8000',
  );

  /// Timeout des requêtes HTTP en secondes.
  static const int httpTimeoutSeconds = 30;

  /// Nombre max de tentatives de PIN avant blocage temporaire.
  static const int maxPinAttempts = 5;

  /// Durée du blocage après échec de PIN, en minutes.
  static const int pinLockoutMinutes = 5;

  /// Largeur du papier d'imprimante thermique en millimètres.
  static const int receiptPaperWidthMm = 58;

  /// Limite de produits par boutique au MVP.
  static const int maxProductsPerStore = 5000;
}
