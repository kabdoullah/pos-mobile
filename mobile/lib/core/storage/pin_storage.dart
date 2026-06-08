import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../config.dart';

/// Storage keys for PIN data.
abstract class _PinStorageKeys {
  /// PIN hash (format `pbkdf2_sha256$<iterations>$<hex>`).
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

  /// PBKDF2 iteration count. Tuned for a slow-enough KDF on a one-shot verify.
  static const int _pbkdf2Iterations = 150000;

  /// Prefix marking the current hash format. Legacy SHA-256 hashes lack it.
  static const String _hashPrefix = 'pbkdf2_sha256';

  /// Saves the PIN as a salted PBKDF2-HMAC-SHA256 hash.
  Future<void> savePinHash(String pin) async {
    // Generate a cryptographically random salt (64 hex chars = 32 bytes).
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

    // Legacy-format hash — reject without counting an attempt; the user must
    // re-setup their PIN (handled by hasPinConfigured at routing time).
    if (!storedHash.startsWith('$_hashPrefix\$')) {
      return false;
    }

    final computedHash = _hashPin(pin, storedSalt);
    final isCorrect = _constantTimeEquals(computedHash, storedHash);

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
  ///
  /// A legacy hash from a previous (insecure) format is treated as absent and
  /// cleared, forcing the user through PIN re-setup.
  Future<bool> hasPinConfigured() async {
    final hash = await _storage.read(key: _PinStorageKeys.pinHash);
    if (hash == null) return false;
    if (!hash.startsWith('$_hashPrefix\$')) {
      // Legacy SHA-256 hash — incompatible, drop it.
      await clearPin();
      return false;
    }
    return true;
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

  /// Hashes a PIN with the given salt using PBKDF2-HMAC-SHA256.
  ///
  /// Returns a self-describing string `pbkdf2_sha256$<iterations>$<hex>` so the
  /// format can be detected and migrated later.
  String _hashPin(String pin, String salt) {
    final derived = _pbkdf2(
      password: utf8.encode(pin),
      salt: _hexDecode(salt),
      iterations: _pbkdf2Iterations,
      keyLength: 32,
    );
    final hex = derived.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    return '$_hashPrefix\$$_pbkdf2Iterations\$$hex';
  }

  /// PBKDF2-HMAC-SHA256 (RFC 8018) over the vetted `crypto` HMAC primitive.
  List<int> _pbkdf2({
    required List<int> password,
    required List<int> salt,
    required int iterations,
    required int keyLength,
  }) {
    final hmac = Hmac(sha256, password);
    const hLen = 32;
    final blockCount = (keyLength / hLen).ceil();
    final output = <int>[];

    for (var i = 1; i <= blockCount; i++) {
      // INT(i): block index as a 4-byte big-endian integer.
      final indexBytes = [
        (i >> 24) & 0xff,
        (i >> 16) & 0xff,
        (i >> 8) & 0xff,
        i & 0xff,
      ];
      var u = hmac.convert([...salt, ...indexBytes]).bytes;
      final block = List<int>.of(u);
      for (var j = 1; j < iterations; j++) {
        u = hmac.convert(u).bytes;
        for (var k = 0; k < hLen; k++) {
          block[k] ^= u[k];
        }
      }
      output.addAll(block);
    }

    return output.sublist(0, keyLength);
  }

  /// Decodes a hex string into bytes.
  List<int> _hexDecode(String hex) {
    final bytes = <int>[];
    for (var i = 0; i < hex.length; i += 2) {
      bytes.add(int.parse(hex.substring(i, i + 2), radix: 16));
    }
    return bytes;
  }

  /// Constant-time string equality — prevents timing-based attacks on PIN hashes.
  bool _constantTimeEquals(String a, String b) {
    if (a.length != b.length) return false;
    var result = 0;
    for (var i = 0; i < a.length; i++) {
      result |= a.codeUnitAt(i) ^ b.codeUnitAt(i);
    }
    return result == 0;
  }

  /// Generates a cryptographically random hex string of [bytes] length.
  String _generateRandomHex(int bytes) {
    final rng = Random.secure();
    final random = List<int>.generate(bytes, (_) => rng.nextInt(256));
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
