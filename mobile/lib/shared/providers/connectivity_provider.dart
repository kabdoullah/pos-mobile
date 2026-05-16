import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'connectivity_provider.g.dart';

/// Provider for app connectivity status.
///
/// Returns true when online, false when offline.
/// Infrastructure for MVP — currently always returns true.
/// TODO: Integrate connectivity_plus for real network monitoring.
@riverpod
bool connectivityStatus(Ref ref) {
  return true;
}
