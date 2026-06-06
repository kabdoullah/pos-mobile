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

  /// Initialise la configuration. À appeler une seule fois avant [runApp].
  static void setup({required AppFlavor flavor, required String apiUrl}) {
    _flavor = flavor;
    _apiUrl = apiUrl;
  }

  /// Environnement actif.
  static AppFlavor get flavor => _flavor;

  /// URL de base de l'API.
  static String get apiUrl => _apiUrl;

  /// Vrai si l'app tourne en mode développement.
  static bool get isDev => _flavor == AppFlavor.dev;

  /// Timeout des requêtes HTTP en secondes.
  /// 60s pour absorber le cold-start Render free tier (~50s).
  static const int httpTimeoutSeconds = 60;

  /// Nombre max de tentatives de PIN avant blocage temporaire.
  static const int maxPinAttempts = 5;

  /// Durée du blocage après échec de PIN, en minutes.
  static const int pinLockoutMinutes = 5;

  /// Largeur du papier d'imprimante thermique en millimètres.
  static const int receiptPaperWidthMm = 58;

  /// Limite de produits par boutique au MVP.
  static const int maxProductsPerStore = 5000;
}
