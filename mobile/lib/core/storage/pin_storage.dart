import 'dart:async';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';

/// Storage keys for PIN data.
abstract class _PinStorageKeys {
  /// PIN hash (SHA-256 hex).
  static const String pinHash = 'pin_hash';

  /// Salt used for PIN hashing (hex).
  static const String pinSalt = 'pin_salt';

  /// Failed PIN attempt count.
  static const String pinAttempts = 'pin_attempts';

  /// Timestamp when PIN lockout expires (ISO 8601).
  static const String pinLockoutUntil = 'pin_lockout_until';
}

/// Stores and verifies a locally-hashed PIN with lockout protection.
class PinStorage {
  /// Creates a PinStorage instance.
  PinStorage({
    FlutterSecureStorage? secureStorage,
    Duration lockoutDuration = const Duration(minutes: 5),
  }) : _storage = secureStorage ?? const FlutterSecureStorage(),
       _lockoutDuration = lockoutDuration;

  /// Underlying secure storage backend.
  final FlutterSecureStorage _storage;

  /// Duration of the PIN lockout after max attempts.
  final Duration _lockoutDuration;

  /// Max PIN attempts before lockout.
  static int get maxAttempts => AppConfig.maxPinAttempts;

  /// Saves the PIN as a SHA-256 hash with a random salt.
  Future<void> savePinHash(String pin) async {
    // Generate a random salt (64 hex chars = 32 bytes).
    final salt = _generateRandomHex(32);
    final hash = _hashPin(pin, salt);

    await Future.wait([
      _storage.write(key: _PinStorageKeys.pinHash, value: hash),
      _storage.write(key: _PinStorageKeys.pinSalt, value: salt),
      _storage.write(key: _PinStorageKeys.pinAttempts, value: '0'),
      _storage.delete(key: _PinStorageKeys.pinLockoutUntil),
    ]);
  }

  /// Verifies a PIN against the stored hash.
  /// Returns true if correct. On failure, increments attempts and triggers
  /// lockout if max attempts exceeded.
  /// Throws [PinLockedException] if PIN is currently locked.
  Future<bool> verifyPin(String pin) async {
    // Check lockout first.
    final (locked: isLocked, remainingSeconds: remaining) =
        await _checkLockout();
    if (isLocked) {
      throw PinLockedException(remainingSeconds: remaining);
    }

    final storedHash = await _storage.read(key: _PinStorageKeys.pinHash);
    final storedSalt = await _storage.read(key: _PinStorageKeys.pinSalt);

    if (storedHash == null || storedSalt == null) {
      return false;
    }

    final computedHash = _hashPin(pin, storedSalt);
    final isCorrect = computedHash == storedHash;

    if (!isCorrect) {
      // Increment attempts.
      final attempts = await getPinAttempts();
      final newAttempts = attempts + 1;

      if (newAttempts >= maxAttempts) {
        // Lock out.
        final lockoutUntil = DateTime.now()
            .add(_lockoutDuration)
            .toIso8601String();
        await _storage.write(
          key: _PinStorageKeys.pinLockoutUntil,
          value: lockoutUntil,
        );
      }

      await _storage.write(
        key: _PinStorageKeys.pinAttempts,
        value: newAttempts.toString(),
      );
    }

    return isCorrect;
  }

  /// Checks if a PIN has been configured.
  Future<bool> hasPinConfigured() async {
    final hash = await _storage.read(key: _PinStorageKeys.pinHash);
    return hash != null;
  }

  /// Gets the current failed PIN attempt count.
  Future<int> getPinAttempts() async {
    final attempts = await _storage.read(key: _PinStorageKeys.pinAttempts);
    if (attempts == null || attempts.isEmpty) return 0;
    return int.tryParse(attempts) ?? 0;
  }

  /// Resets the PIN attempt counter and clears lockout.
  Future<void> resetAttempts() async {
    await Future.wait([
      _storage.write(key: _PinStorageKeys.pinAttempts, value: '0'),
      _storage.delete(key: _PinStorageKeys.pinLockoutUntil),
    ]);
  }

  /// Clears all PIN-related data.
  Future<void> clearPin() async {
    await Future.wait([
      _storage.delete(key: _PinStorageKeys.pinHash),
      _storage.delete(key: _PinStorageKeys.pinSalt),
      _storage.delete(key: _PinStorageKeys.pinAttempts),
      _storage.delete(key: _PinStorageKeys.pinLockoutUntil),
    ]);
  }

  /// Checks if PIN is currently locked due to too many failed attempts.
  /// Returns tuple with (locked, remainingSeconds).
  Future<({bool locked, int remainingSeconds})> _checkLockout() async {
    final lockoutStr = await _storage.read(
      key: _PinStorageKeys.pinLockoutUntil,
    );
    if (lockoutStr == null) {
      return (locked: false, remainingSeconds: 0);
    }

    try {
      final lockoutUntil = DateTime.parse(lockoutStr);
      final now = DateTime.now();

      if (now.isAfter(lockoutUntil)) {
        // Lockout expired, clear it.
        await _storage.delete(key: _PinStorageKeys.pinLockoutUntil);
        return (locked: false, remainingSeconds: 0);
      }

      final remaining = lockoutUntil.difference(now).inSeconds;
      return (locked: true, remainingSeconds: remaining);
    } catch (_) {
      // Malformed timestamp, clear it.
      await _storage.delete(key: _PinStorageKeys.pinLockoutUntil);
      return (locked: false, remainingSeconds: 0);
    }
  }

  /// Hashes a PIN with the given salt using SHA-256.
  String _hashPin(String pin, String salt) {
    final input = '$salt$pin';
    return sha256.convert(utf8.encode(input)).toString();
  }

  /// Generates a random hex string of [bytes] length (2 chars per byte).
  String _generateRandomHex(int bytes) {
    final random = List<int>.generate(
      bytes,
      (i) => DateTime.now().microsecond % 256,
    );
    return random.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }
}

/// Thrown when PIN verification is blocked due to too many failed attempts.
class PinLockedException implements Exception {
  /// Creates a PinLockedException.
  PinLockedException({required this.remainingSeconds});

  /// Seconds until the lockout expires.
  final int remainingSeconds;

  @override
  String toString() => 'PIN verrouillé. Réessayez dans $remainingSeconds s.';
}
