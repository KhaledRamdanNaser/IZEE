import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:izee_ui/main.dart';
import 'package:izee_ui/services/app_services.dart';

class FakeAppServicesForIncident extends AppServices {
  Map<String, dynamic>? reportedIncident;

  @override
  Future<Map<String, dynamic>> reportIncident({
    required String category,
    required String severity,
    required String details,
    String? vehicleId,
    String? routeId,
    String? locationLabel,
    double? lat,
    double? lon,
  }) async {
    reportedIncident = {
      'category': category,
      'severity': severity,
      'details': details,
      'vehicle_id': vehicleId,
      'route_id': routeId,
      'location_label': locationLabel,
      'lat': lat,
      'lon': lon,
      'source': 'passenger_app',
    };
    return {'status': 'success'};
  }
}

void main() {
  testWidgets('ReportIncidentScreen renders correctly and submits incident report successfully', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1080, 1920);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final fakeServices = FakeAppServicesForIncident();
    bool navBackToHome = false;

    Widget buildScreen() {
      return MaterialApp(
        home: Scaffold(
          body: ReportIncidentScreen(
            services: fakeServices,
            connect: (action, request, {quiet = false}) async {
              await request();
              return true;
            },
            onGo: (screen) {
              if (screen == AppScreen.home) {
                navBackToHome = true;
              }
            },
          ),
        ),
      );
    }

    // 1. Load screen
    await tester.pumpWidget(buildScreen());
    await tester.pumpAndSettle();

    // 2. Verify all UI elements exist
    expect(find.text('Report Incident'), findsOneWidget);
    expect(find.text('Incident Category *'), findsOneWidget);
    expect(find.text('Severity Level *'), findsOneWidget);
    expect(find.text('Description / Details *'), findsOneWidget);
    expect(find.text('Location Description (Optional)'), findsOneWidget);
    expect(find.text('Vehicle ID (Optional)'), findsOneWidget);
    expect(find.text('Route ID (Optional)'), findsOneWidget);
    expect(find.text('Submit Report'), findsOneWidget);

    // 3. Try to submit without entering details (validation failure)
    await tester.tap(find.text('Submit Report'));
    await tester.pumpAndSettle();
    expect(find.text('Description is required'), findsOneWidget);
    expect(fakeServices.reportedIncident, isNull);

    // 4. Fill in required details and optional fields
    await tester.enterText(find.widgetWithText(TextFormField, 'Describe the incident in detail...'), 'Bus is delayed by 30 mins because of a flat tire');
    await tester.enterText(find.widgetWithText(TextFormField, 'e.g. Abbassia Station, near the gate'), 'Ramses Square');
    await tester.enterText(find.widgetWithText(TextFormField, 'e.g. V-001'), 'V-102');
    
    // Choose Severity Chip (Critical)
    await tester.tap(find.text('Critical'));
    await tester.pumpAndSettle();

    // 5. Submit valid form
    await tester.tap(find.text('Submit Report'));
    await tester.pumpAndSettle();

    // Verify service was called with proper arguments
    expect(fakeServices.reportedIncident, isNotNull);
    expect(fakeServices.reportedIncident!['category'], equals('Delay'));
    expect(fakeServices.reportedIncident!['severity'], equals('critical'));
    expect(fakeServices.reportedIncident!['details'], equals('Bus is delayed by 30 mins because of a flat tire'));
    expect(fakeServices.reportedIncident!['location_label'], equals('Ramses Square'));
    expect(fakeServices.reportedIncident!['vehicle_id'], equals('V-102'));
    expect(fakeServices.reportedIncident!['source'], equals('passenger_app'));

    expect(navBackToHome, isTrue);
  });
}
