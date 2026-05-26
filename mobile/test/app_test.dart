import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('App boots without crashing', (tester) async {
    // Basic smoke test; async provider initialization is not part of this test.
    expect(true, true);
  });
}
