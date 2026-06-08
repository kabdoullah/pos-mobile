/// Environnement de déploiement de l'application.
enum AppFlavor {
  /// Développement local — API staging, logs verbeux, banner debug.
  dev,

  /// Production — API prod, pas de banner debug.
  prod,
}

/// Configuration globale de l'application.
///
/// Initialisée via [AppConfig.setup] dans le point d'entrée (main_*.dart)
/// avant tout appel à [runApp].
class AppConfig {
  AppConfig._();

  static late final AppFlavor _flavor;
  static late final String _apiUrl;

  static late final int _httpConnectTimeoutSeconds;
  static late final int _httpReceiveTimeoutSeconds;

  /// Initialise la configuration. À appeler une seule fois avant [runApp].
  static void setup({required AppFlavor flavor, required String apiUrl}) {
    _flavor = flavor;
    _apiUrl = apiUrl;
    // 60s en dev pour le cold-start Render free tier (~50s). Valeurs courtes en prod.
    _httpConnectTimeoutSeconds = flavor == AppFlavor.dev ? 60 : 10;
    _httpReceiveTimeoutSeconds = flavor == AppFlavor.dev ? 60 : 30;
  }

  /// Environnement actif.
  static AppFlavor get flavor => _flavor;

  /// URL de base de l'API.
  static String get apiUrl => _apiUrl;

  /// Vrai si l'app tourne en mode développement.
  static bool get isDev => _flavor == AppFlavor.dev;

  /// Timeout de connexion TCP en secondes (10s prod, 60s dev).
  static int get httpConnectTimeoutSeconds => _httpConnectTimeoutSeconds;

  /// Timeout de réception HTTP en secondes (30s prod, 60s dev).
  static int get httpReceiveTimeoutSeconds => _httpReceiveTimeoutSeconds;

  /// Nombre max de tentatives de PIN avant blocage temporaire.
  static const int maxPinAttempts = 5;

  /// Durée du blocage après échec de PIN, en minutes.
  static const int pinLockoutMinutes = 5;

  /// Largeur du papier d'imprimante thermique en millimètres.
  static const int receiptPaperWidthMm = 58;

  /// Limite de produits par boutique au MVP.
  static const int maxProductsPerStore = 5000;
}
