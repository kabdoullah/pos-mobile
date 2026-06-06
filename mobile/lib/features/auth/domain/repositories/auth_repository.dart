import '../entities/user.dart';

/// Interface du repository auth. Implémenté dans la couche `data`.
abstract class AuthRepository {
  /// Crée un compte utilisateur.
  Future<User> register({
    required String email,
    required String password,
    required String phoneNumber,
  });

  /// Authentifie via email + mot de passe.
  /// Stocke les tokens en secure storage.
  Future<User> login({required String email, required String password});

  /// Définit le PIN local après la première connexion.
  Future<void> setupPin(String pin);

  /// Vérifie le PIN saisi par l'utilisateur.
  /// Retourne true si correct, false sinon.
  Future<bool> verifyPin(String pin);

  /// Récupère le nombre d'échecs de PIN actuels.
  Future<int> getPinAttempts();

  /// Réinitialise le compteur d'échecs de PIN après réussite.
  Future<void> resetPinAttempts();

  /// Demande un email de réinitialisation de mot de passe.
  Future<void> sendPasswordReset(String email);

  /// Déconnecte l'utilisateur (efface tokens et PIN).
  Future<void> logout();

  /// Récupère l'utilisateur courant si authentifié.
  Future<User?> getCurrentUser();

  /// True si un PIN est défini sur cet appareil.
  Future<bool> hasPinSetup();

  /// Rafraîchit l'access token via le refresh token stocké.
  /// Nécessaire après création de boutique pour obtenir un token avec store_id.
  Future<void> refreshTokens();
}
