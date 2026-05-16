import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../domain/entities/user.dart';

part 'auth_providers.g.dart';

/// État d'authentification actuel.
sealed class AuthState {
  const AuthState();
}

/// Aucun utilisateur authentifié.
class AuthStateUnauthenticated extends AuthState {
  /// Constructor.
  const AuthStateUnauthenticated();
}

/// Utilisateur authentifié mais PIN pas encore vérifié.
class AuthStatePinRequired extends AuthState {
  /// Constructor.
  const AuthStatePinRequired();
}

/// Utilisateur authentifié et PIN vérifié.
class AuthStateAuthenticated extends AuthState {
  /// Constructor.
  const AuthStateAuthenticated(this.user);

  /// Utilisateur courant.
  final User user;
}

/// Authentification en cours.
class AuthStateLoading extends AuthState {
  /// Constructor.
  const AuthStateLoading();
}

/// Erreur d'authentification.
class AuthStateError extends AuthState {
  /// Constructor.
  const AuthStateError(this.message);

  /// Message d'erreur.
  final String message;
}

/// Provider de l'état d'authentification global.
@riverpod
class Auth extends _$Auth {
  @override
  AuthState build() {
    // TODO: Initialize auth state by checking for existing JWT tokens
    // and PIN configuration in secure storage.
    // For now, start unauthenticated.
    return const AuthStateUnauthenticated();
  }

  /// Authentifie via email + mot de passe.
  Future<void> login(String email, String password) async {
    state = const AuthStateLoading();
    try {
      // TODO: Call authRepository.login(email, password).
      // This should store JWT tokens in flutter_secure_storage.
      // For now, just transition to PIN required state.
      state = const AuthStatePinRequired();
    } catch (e) {
      state = AuthStateError(e.toString());
    }
  }

  /// Enregistre un nouvel utilisateur.
  Future<void> register(
    String email,
    String password,
    String phoneNumber,
  ) async {
    state = const AuthStateLoading();
    try {
      // TODO: Call authRepository.register(email, password, phoneNumber).
      // This should create the user account and store JWT tokens.
      // For now, just transition to PIN setup state (PinRequired).
      state = const AuthStatePinRequired();
    } catch (e) {
      state = AuthStateError(e.toString());
    }
  }

  /// Vérifie le PIN de l'utilisateur.
  Future<void> verifyPin(String pin) async {
    state = const AuthStateLoading();
    try {
      // TODO: Call authRepository.verifyPin(pin).
      // For now, just transition to authenticated (with dummy user).
      const user = User(
        id: '00000000-0000-0000-0000-000000000000',
        email: 'demo@example.com',
        phoneNumber: '+225 0123456789',
      );
      state = AuthStateAuthenticated(user);
    } catch (e) {
      state = AuthStateError(e.toString());
    }
  }

  /// Configure le PIN après la première connexion.
  Future<void> setupPin(String pin) async {
    state = const AuthStateLoading();
    try {
      // TODO: Call authRepository.setupPin(pin).
      // For now, just transition to authenticated.
      const user = User(
        id: '00000000-0000-0000-0000-000000000000',
        email: 'demo@example.com',
        phoneNumber: '+225 0123456789',
      );
      state = AuthStateAuthenticated(user);
    } catch (e) {
      state = AuthStateError(e.toString());
    }
  }

  /// Déconnecte l'utilisateur courant.
  void logout() {
    state = const AuthStateUnauthenticated();
  }
}
