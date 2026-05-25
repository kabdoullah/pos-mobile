import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'nav_provider.g.dart';

/// Manages the currently selected bottom navigation tab index.
@riverpod
class BottomNavIndex extends _$BottomNavIndex {
  @override
  int build() => 0; // Default to home (index 0)

  /// Set the navigation index.
  void setIndex(int index) => state = index;
}
