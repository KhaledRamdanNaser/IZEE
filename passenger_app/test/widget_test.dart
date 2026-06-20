import 'package:flutter_test/flutter_test.dart';
import 'package:izee_ui/main.dart';

void main() {
  testWidgets('IZEE app opens through splash and login', (tester) async {
    await tester.pumpWidget(const IzeeApp());

    expect(find.text('IZEE'), findsOneWidget);
    expect(find.text('Smart Public Transport'), findsOneWidget);
    expect(find.text('Get Started'), findsOneWidget);

    await tester.tap(find.text('Get Started'));
    await tester.pumpAndSettle();

    expect(find.text('Login'), findsWidgets);
    await tester.tap(find.text('Login').last);
    await tester.pumpAndSettle();

    expect(find.text('Nearby Buses'), findsOneWidget);
    expect(find.text('Where do you want to go?'), findsOneWidget);
  });
}
