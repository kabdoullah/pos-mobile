import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/network/network_providers.dart';
import '../../domain/entities/user.dart';
import '../../../auth/providers/auth_di_providers.dart';

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

/// Utilisateur authentifié mais PIN pas encore configuré (première connexion).
class AuthStatePinSetupRequired extends AuthState {
  /// Constructor.
  const AuthStatePinSetupRequired();
}

/// Utilisateur authentifié mais PIN pas encore vérifié (PIN configuré, vérification requise).
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
    // Listen for token expiry from refresh interceptor.
    final expiredController = ref.watch(authExpiredControllerProvider);
    final sub = expiredController.stream.listen((_) {
      state = const AuthStateUnauthenticated();
    });
    ref.onDispose(sub.cancel);

    // Initialize auth state asynchronously.
    _initializeAuthState();
    return const AuthStateLoading();
  }

  /// Initializes auth state by checking for existing tokens and PIN config.
  Future<void> _initializeAuthState() async {
    try {
      final repo = ref.read(authRepositoryProvider);
      final user = await repo.getCurrentUser();

      if (user == null) {
        state = const AuthStateUnauthenticated();
        return;
      }

      final hasPinSetup = await repo.hasPinSetup();
      state = hasPinSetup
          ? const AuthStatePinRequired()
          : const AuthStatePinSetupRequired();
    } catch (_) {
      state = const AuthStateUnauthenticated();
    }
  }

  /// Authentifie via email + mot de passe.
  Future<void> login(String email, String password) async {
    state = const AuthStateLoading();
    try {
      final repo = ref.read(authRepositoryProvider);
      await repo.login(email: email, password: password);
      final hasPinSetup = await repo.hasPinSetup();

      if (hasPinSetup) {
        state = const AuthStatePinRequired();
      } else {
        state = const AuthStatePinSetupRequired();
      }
    } catch (e) {
      final message = _userFriendlyError(e);
      state = AuthStateError(message);
      rethrow;
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
      final repo = ref.read(authRepositoryProvider);
      await repo.register(
        email: email,
        password: password,
        phoneNumber: phoneNumber,
      );
      final hasPinSetup = await repo.hasPinSetup();

      if (hasPinSetup) {
        state = const AuthStatePinRequired();
      } else {
        state = const AuthStatePinSetupRequired();
      }
    } catch (e) {
      final message = _userFriendlyError(e);
      state = AuthStateError(message);
      rethrow;
    }
  }

  /// Vérifie le PIN de l'utilisateur.
  Future<void> verifyPin(String pin) async {
    state = const AuthStateLoading();
    try {
      final repo = ref.read(authRepositoryProvider);
      final isCorrect = await repo.verifyPin(pin);

      if (!isCorrect) {
        throw Exception('PIN incorrect');
      }

      final user = await repo.getCurrentUser();
      if (user != null) {
        state = AuthStateAuthenticated(user);
      } else {
        state = const AuthStateUnauthenticated();
      }
    } catch (e) {
      final message = _userFriendlyError(e);
      state = AuthStateError(message);
      rethrow;
    }
  }

  /// Configure le PIN après la première connexion.
  Future<void> setupPin(String pin) async {
    state = const AuthStateLoading();
    try {
      final repo = ref.read(authRepositoryProvider);
      await repo.setupPin(pin);
      await repo.resetPinAttempts();

      final user = await repo.getCurrentUser();
      if (user != null) {
        state = AuthStateAuthenticated(user);
      } else {
        state = const AuthStateUnauthenticated();
      }
    } catch (e) {
      final message = _userFriendlyError(e);
      state = AuthStateError(message);
      rethrow;
    }
  }

  /// Déconnecte l'utilisateur courant.
  Future<void> logout() async {
    try {
      final repo = ref.read(authRepositoryProvider);
      await repo.logout();
    } finally {
      state = const AuthStateUnauthenticated();
    }
  }

  /// Converts exception to user-friendly error message.
  String _userFriendlyError(Object e) {
    final str = e.toString();
    if (str.contains('email')) return 'Email déjà utilisé';
    if (str.contains('password')) return 'Email ou mot de passe incorrect';
    if (str.contains('connection')) return 'Pas de connexion';
    if (str.contains('timeout')) return 'Délai dépassé';
    if (str.contains('verrouillé')) return str;
    return str;
  }
}
