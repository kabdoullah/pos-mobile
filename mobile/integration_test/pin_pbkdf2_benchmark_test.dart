// On-device benchmark for the PBKDF2-HMAC-SHA256 PIN KDF.
//
// Run on a real device to size `_pbkdf2Iterations` in PinStorage against the
// actual unlock latency users will feel:
//
//   flutter test integration_test/pin_pbkdf2_benchmark_test.dart -d <device-id>
//
// This is a measurement harness, not a pass/fail test. It mirrors the exact
// PBKDF2 loop used in PinStorage so the timings reflect production cost.
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

/// PBKDF2-HMAC-SHA256, identical to PinStorage._pbkdf2.
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

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  test('PBKDF2 iteration-count timing sweep', () {
    final pin = utf8.encode('1234');
    final salt = List<int>.generate(32, (i) => i);
    const iterationCounts = [50000, 100000, 150000, 200000, 300000];
    const repeats = 5;

    // Warm up the JIT/AOT paths so the first run isn't penalised.
    _pbkdf2(password: pin, salt: salt, iterations: 10000, keyLength: 32);

    // ignore: avoid_print
    print('=== PBKDF2-HMAC-SHA256 on-device benchmark ===');
    for (final iterations in iterationCounts) {
      final samples = <int>[];
      for (var r = 0; r < repeats; r++) {
        final sw = Stopwatch()..start();
        _pbkdf2(
          password: pin,
          salt: salt,
          iterations: iterations,
          keyLength: 32,
        );
        sw.stop();
        samples.add(sw.elapsedMilliseconds);
      }
      samples.sort();
      final median = samples[samples.length ~/ 2];
      final min = samples.first;
      final max = samples.last;
      // ignore: avoid_print
      print(
        'iterations=$iterations  median=${median}ms  '
        'min=${min}ms  max=${max}ms  samples=$samples',
      );
    }
  });
}
