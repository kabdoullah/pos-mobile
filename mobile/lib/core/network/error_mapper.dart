import 'api_exception.dart';

const _detailMap = <String, String>{
  // Auth
  'This phone number is already registered.': 'Ce numéro est déjà enregistré.',
  'This email is already registered.': 'Cet email est déjà enregistré.',
  'Invalid phone number or password.': 'Numéro ou mot de passe incorrect.',
  'Invalid email or password.': 'Email ou mot de passe incorrect.',
  'Account is disabled.': 'Le compte est désactivé.',
  'Invalid or expired refresh token.':
      'Session expirée, veuillez vous reconnecter',
  'User not found or disabled.': 'Utilisateur introuvable ou désactivé',
  'Invalid or expired token.': 'Lien invalide ou expiré',
  'Not authenticated': 'Authentification requise',
  'Invalid credentials': 'Session expirée, veuillez vous reconnecter',
  // Catalog
  'Product not found.': 'Produit introuvable',
  'A product with this barcode already exists.':
      'Un produit avec ce code-barres existe déjà',
  // Sales
  'Sale not found.': 'Vente introuvable',
  // Stores
  'Store not found.': 'Boutique introuvable',
  'A store already exists for this user.':
      'Une boutique existe déjà pour cet utilisateur',
  // Sync
  'since must be timezone-aware': 'Paramètre de date invalide',
};

/// Maps any exception to a French user-facing message.
String errorToFrench(Object e) {
  if (e is ApiException) {
    return _detailMap[e.message] ?? 'Une erreur est survenue.';
  }
  if (e is ConnectionException) {
    return e.message; // already French
  }
  return 'Une erreur est survenue.';
}
