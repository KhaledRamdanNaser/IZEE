import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:izee_ui/main.dart';
import 'package:izee_ui/services/app_services.dart';

void main() {
  test('PlanTripSession default settings and Leave Now/Schedule stores departure datetime', () {
    final session = PlanTripSession();
    expect(session.isLeaveNow, true);
    expect(session.selectedDepartureDateTime, isNull);

    // Set to Leave Now explicitly
    session.isLeaveNow = true;
    session.selectedDepartureDateTime = DateTime.now();
    expect(session.isLeaveNow, true);
    expect(session.selectedDepartureDateTime, isNotNull);

    // Schedule picker simulation
    final scheduledTime = DateTime.now().add(const Duration(hours: 2));
    session.isLeaveNow = false;
    session.selectedDepartureDateTime = scheduledTime;
    expect(session.isLeaveNow, false);
    expect(session.selectedDepartureDateTime, scheduledTime);
  });

  testWidgets('PlanTripScreen opens and displays Leave Now by default', (WidgetTester tester) async {
    final session = PlanTripSession();
    final services = AppServices();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: PlanTripScreen(
            services: services,
            connect: (action, request, {quiet = false}) async => true,
            onGo: (screen) {},
            session: session,
            onRouteSelected: (route) {},
          ),
        ),
      ),
    );

    // Find the Leaving now button/chip
    expect(find.text('Leaving now'), findsOneWidget);
    expect(find.text('Schedule'), findsOneWidget);

    // Tap Schedule button
    await tester.tap(find.text('Schedule'));
    await tester.pump();

    // Verify calendar picker dialog is opened
    expect(find.byType(CalendarDatePicker), findsOneWidget);
  });
}
