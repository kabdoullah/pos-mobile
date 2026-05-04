import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile/core/app.dart';


void main() {
  testWidgets('App boots without crashing', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(child: PosMobileApp()),
    );

    // Vérifie que le titre principal est présent
    expect(find.text('POS Mobile CI'), findsAtLeastNWidgets(1));
  });
}
