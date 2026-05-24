import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:logger/logger.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../core/network/network_providers.dart';
import '../../domain/entities/user.dart';
import '../../../auth/providers/auth_di_providers.dart';

part 'auth_providers.g.dart';

/// Authentication status — the user's position in the auth flow.
///
/// Lifecycle: `Unauthenticated` → (after login) → `StoreSetupRequired`/`PinSetupRequired`/`PinRequired` → `Authenticated`.
/// Or: any state + token expiry → `Unauthenticated`.
sealed class AuthStatus {
  /// Constructor.
  const AuthStatus();
}

/// No valid token in secure storage. User must log in or register.
class AuthUnauthenticated extends AuthStatus {
  /// Constructor.
  const AuthUnauthenticated();
}

/// Token valid + user authenticated, but store not yet configured (first registration only).
/// After store setup → `PinSetupRequired`.
class AuthStoreSetupRequired extends AuthStatus {
  /// Constructor.
  const AuthStoreSetupRequired();
}

/// Token valid + user authenticated, but PIN not yet created on this device (first login only).
/// After PIN creation → `Authenticated`.
class AuthPinSetupRequired extends AuthStatus {
  /// Constructor.
  const AuthPinSetupRequired();
}

/// Token valid + user authenticated, PIN exists locally, but not yet verified in this session.
/// User must unlock via PIN verification → `Authenticated`.
class AuthPinRequired extends AuthStatus {
  /// Constructor.
  const AuthPinRequired();
}

/// Token valid + user authenticated + PIN verified in this session.
/// User has full access to app.
class AuthAuthenticated extends AuthStatus {
  /// Creates an authenticated status.
  const AuthAuthenticated(this.user);

  /// The authenticated user (extracted from JWT claims).
  final User user;
}

/// Manages authentication state and actions (login, register, PIN setup/verify, logout).
///
/// State is `AsyncValue<AuthStatus>`:
/// - `AsyncLoading`: operation in progress (init, login, register, PIN verify, etc.)
/// - `AsyncData(status)`: operation succeeded, user is in `status`
/// - `AsyncError(exception)`: operation failed, exception is user-friendly message (see [_toUserFacingException])
///
/// Init sequence: On app launch, `build()` checks secure storage for tokens + PIN config, then routes accordingly.
/// Token expiry is handled via [authExpiredControllerProvider] stream — when server invalidates token,
/// this notifier transitions to `Unauthenticated`, router detects change and redirects to login.
@riverpod
class Auth extends _$Auth {
  static final _logger = Logger();

  @override
  Future<AuthStatus> build() async {
    _logger.i('[Auth.build] Initializing auth state');

    // Listen for token expiry events from Dio refresh interceptor.
    // When interceptor detects 401 + failed refresh, it emits to this stream.
    final expiredController = ref.watch(authExpiredControllerProvider);
    // StreamSubscription is closed in onDispose — linter false positive below
    final sub = expiredController.stream.listen((_) {
      _logger.w('[Auth] Token expired detected, resetting to Unauthenticated');
      state = const AsyncData(AuthUnauthenticated());
    });
    ref.onDispose(sub.cancel);

    // Async init (direct — no fire-and-forget hack needed in AsyncNotifier).
    return _resolveInitialStatus();
  }

  /// Check stored tokens + PIN config to determine initial state on app launch.
  Future<AuthStatus> _resolveInitialStatus() async {
    try {
      final repo = ref.read(authRepositoryProvider);
      final user = await repo.getCurrentUser();

      if (user == null) {
        _logger.i(
          '[Auth._resolveInitialStatus] No stored token, returning Unauthenticated',
        );
        return const AuthUnauthenticated();
      }

      final hasPinSetup = await repo.hasPinSetup();
      final status = hasPinSetup
          ? const AuthPinRequired()
          : const AuthPinSetupRequired();
      _logger.i(
        '[Auth._resolveInitialStatus] Token found, PIN configured=$hasPinSetup, returning $status',
      );
      return status;
    } catch (e) {
      _logger.e(
        '[Auth._resolveInitialStatus] Init failed: $e, returning Unauthenticated',
      );
      return const AuthUnauthenticated();
    }
  }

  /// Authenticate user with email + password.
  ///
  /// Calls backend login endpoint, saves JWT tokens to secure storage.
  /// Then checks PIN config: if yes → PinRequired (verify existing PIN), if no → PinSetupRequired (create new PIN).
  /// Errors are automatically captured in `AsyncError` via [AsyncValue.guard].
  Future<void> login(String email, String password) async {
    _logger.i('[Auth.login] Starting for $email');
    state = const AsyncLoading<AuthStatus>();

    state = await AsyncValue.guard(() async {
      try {
        final repo = ref.read(authRepositoryProvider);
        await repo.login(email: email, password: password);
        _logger.i('[Auth.login] Backend login succeeded');

        final hasPinSetup = await repo.hasPinSetup();
        final status = hasPinSetup
            ? const AuthPinRequired()
            : const AuthPinSetupRequired();
        _logger.i(
          '[Auth.login] PIN configured=$hasPinSetup, transitioning to $status',
        );
        return status;
      } catch (e) {
        final msg = _toUserFacingException(e);
        _logger.e('[Auth.login] Failed: $msg');
        throw msg;
      }
    });
  }

  /// Register a new user account (email + password + phone).
  ///
  /// Creates account on backend, saves tokens to secure storage.
  /// Transitions to `StoreSetupRequired` (user must configure store name, address, VAT status).
  /// After store setup → `PinSetupRequired`.
  Future<void> register(
    String email,
    String password,
    String phoneNumber,
  ) async {
    _logger.i('[Auth.register] Starting for $email');
    state = const AsyncLoading<AuthStatus>();

    state = await AsyncValue.guard(() async {
      try {
        final repo = ref.read(authRepositoryProvider);
        await repo.register(
          email: email,
          password: password,
          phoneNumber: phoneNumber,
        );
        _logger.i('[Auth.register] Backend registration succeeded');
        return const AuthStoreSetupRequired();
      } catch (e) {
        final msg = _toUserFacingException(e);
        _logger.e('[Auth.register] Failed: $msg');
        throw msg;
      }
    });
  }

  /// Verify user's 4-digit PIN for daily session unlock.
  ///
  /// Checks PIN against bcrypt hash in local secure storage.
  /// On success: fetches current user from token → `Authenticated`.
  /// On PIN mismatch: throws "PIN incorrect".
  /// On 5th attempt: local storage auto-lockout for 5 minutes.
  Future<void> verifyPin(String pin) async {
    _logger.i('[Auth.verifyPin] Attempt with PIN length=${pin.length}');
    state = const AsyncLoading<AuthStatus>();

    state = await AsyncValue.guard(() async {
      try {
        final repo = ref.read(authRepositoryProvider);
        final isCorrect = await repo.verifyPin(pin);

        if (!isCorrect) {
          throw 'PIN incorrect';
        }

        _logger.i('[Auth.verifyPin] PIN verified, fetching user');
        final user = await repo.getCurrentUser();
        if (user != null) {
          _logger.i(
            '[Auth.verifyPin] User found, transitioning to Authenticated',
          );
          return AuthAuthenticated(user);
        } else {
          _logger.w(
            '[Auth.verifyPin] User not found despite valid PIN, returning Unauthenticated',
          );
          return const AuthUnauthenticated();
        }
      } catch (e) {
        if (e is Exception && e.toString().contains('PIN verrouillé')) {
          // PinLockedException from repo — keep exact message
          _logger.e('[Auth.verifyPin] PIN locked: $e');
          rethrow;
        }
        final msg = _toUserFacingException(e);
        _logger.e('[Auth.verifyPin] Failed: $msg');
        throw msg;
      }
    });
  }

  /// User has navigated past store setup (from store_setup_page.dart).
  /// Immediately transition to PIN setup screen.
  /// Synchronous — no network call, just state machine transition.
  void proceedToPinSetup() {
    _logger.i('[Auth.proceedToPinSetup] Transitioning to PinSetupRequired');
    state = const AsyncData(AuthPinSetupRequired());
  }

  /// Create a new 4-digit PIN (after first login).
  ///
  /// Saves PIN hash + salt to local secure storage.
  /// Resets PIN attempt counter.
  /// Then transitions to `Authenticated`.
  Future<void> setupPin(String pin) async {
    _logger.i('[Auth.setupPin] Setting PIN with length=${pin.length}');
    state = const AsyncLoading<AuthStatus>();

    state = await AsyncValue.guard(() async {
      try {
        final repo = ref.read(authRepositoryProvider);
        await repo.setupPin(pin);
        await repo.resetPinAttempts();
        _logger.i(
          '[Auth.setupPin] PIN saved, resetting attempts, fetching user',
        );

        final user = await repo.getCurrentUser();
        if (user != null) {
          _logger.i(
            '[Auth.setupPin] User found, transitioning to Authenticated',
          );
          return AuthAuthenticated(user);
        } else {
          _logger.w(
            '[Auth.setupPin] User not found despite valid token, returning Unauthenticated',
          );
          return const AuthUnauthenticated();
        }
      } catch (e) {
        final msg = _toUserFacingException(e);
        _logger.e('[Auth.setupPin] Failed: $msg');
        throw msg;
      }
    });
  }

  /// Log out the current user.
  ///
  /// Clears tokens from secure storage + PIN from local storage.
  /// Always transitions to `Unauthenticated`, even if clear fails.
  Future<void> logout() async {
    _logger.i('[Auth.logout] Logging out');
    try {
      final repo = ref.read(authRepositoryProvider);
      await repo.logout();
      _logger.i('[Auth.logout] Storage cleared');
    } finally {
      state = const AsyncData(AuthUnauthenticated());
    }
  }

  /// Convert exceptions to user-friendly French messages.
  /// Used inside [AsyncValue.guard] to store meaningful errors.
  String _toUserFacingException(Object e) {
    final message = e is NetworkException ? e.message : e.toString();

    if (message.toLowerCase().contains('email')) return 'Email déjà utilisé';
    if (message.toLowerCase().contains('password')) {
      return 'Email ou mot de passe incorrect';
    }
    if (message.toLowerCase().contains('connection')) return 'Pas de connexion';
    if (message.toLowerCase().contains('timeout')) return 'Délai dépassé';
    if (message.toLowerCase().contains('verrouillé')) {
      return message; // PIN lockout
    }
    return message;
  }
}
