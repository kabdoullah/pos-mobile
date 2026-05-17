import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'connectivity_provider.g.dart';

/// Real-time app connectivity status stream provider.
///
/// Returns true when online, false when offline.
/// Uses connectivity_plus to monitor network changes.
@Riverpod(keepAlive: true)
Stream<bool> isOnline(Ref ref) async* {
  final connectivity = Connectivity();

  // Emit initial state.
  final initial = await connectivity.checkConnectivity();
  yield _isConnected(initial);

  // Stream changes.
  yield* connectivity.onConnectivityChanged.map(_isConnected);
}

bool _isConnected(List<ConnectivityResult> results) =>
    results.any((r) => r != ConnectivityResult.none);
