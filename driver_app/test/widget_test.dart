import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:izee_driver/main.dart';
import 'package:izee_driver/services/driver_services.dart';

void main() {
  testWidgets('driver login opens dashboard', (tester) async {
    tester.view.physicalSize = const Size(800, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const IzeeDriverApp());

    expect(find.text('IZEE Driver'), findsOneWidget);
    expect(find.text('Secure Login'), findsOneWidget);
    expect(find.text('Sign In'), findsOneWidget);

    await tester.ensureVisible(find.text('Use Biometric Login'));
    await tester.tap(find.text('Use Biometric Login'));
    await tester.pumpAndSettle();

    expect(find.text('Trip Active'), findsOneWidget);
    expect(find.text('View Map'), findsOneWidget);
    expect(find.text('Route Info'), findsOneWidget);
    expect(find.text('Report Issue'), findsOneWidget);
    expect(find.text('Messages'), findsOneWidget);
  });

  testWidgets('profile shows connected logout action', (tester) async {
    tester.view.physicalSize = const Size(800, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const IzeeDriverApp());

    await tester.ensureVisible(find.text('Use Biometric Login'));
    await tester.tap(find.text('Use Biometric Login'));
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.person));
    await tester.pumpAndSettle();

    expect(find.text('Driver Profile'), findsOneWidget);

    await tester.dragUntilVisible(
      find.text('Logout'),
      find.byType(ListView),
      const Offset(0, -300),
    );
    expect(find.text('Logout'), findsOneWidget);
  });

  testWidgets('live map renders assigned route data on a small phone viewport',
      (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final services = DriverServices();
    addTearDown(services.dispose);
    services.routeState.value = {
      'route_id': 'A-12 Express',
      'route_name': 'A-12 Express',
      'origin': 'Downtown Terminal',
      'destination': 'Cairo Stadium',
      'current_stop_sequence': 2,
      'total_stops': 4,
      'progress_percent': 50,
      'status': 'active',
      'stops': [
        {
          'name': 'Downtown Terminal',
          'scheduled_time': '08:15 AM',
          'status': 'completed',
          'distance_km': 0,
          'sequence': 1,
          'lat': 30.0444,
          'lon': 31.2357,
        },
        {
          'name': 'Ramses Square Stop',
          'scheduled_time': '08:25 AM',
          'status': 'next',
          'distance_km': 3.5,
          'sequence': 2,
          'lat': 30.0626,
          'lon': 31.2460,
        },
        {
          'name': 'Abbaseya Station',
          'scheduled_time': '08:35 AM',
          'status': 'upcoming',
          'distance_km': 6.2,
          'sequence': 3,
          'lat': 30.0713,
          'lon': 31.2805,
        },
        {
          'name': 'Cairo Stadium Station',
          'scheduled_time': '08:45 AM',
          'status': 'upcoming',
          'distance_km': 8.5,
          'sequence': 4,
          'lat': 30.0737,
          'lon': 31.3113,
        },
      ],
    };

    await tester.pumpWidget(
      MaterialApp(
        home: LiveMapScreen(services: services),
      ),
    );
    await tester.pump();

    expect(find.text('Live Map'), findsOneWidget);
    expect(find.byType(DriverMapCanvas), findsOneWidget);
    expect(find.text('Location Sharing'), findsOneWidget);
    expect(find.text('Current Speed'), findsOneWidget);
    expect(find.text('Current Location'), findsOneWidget);

    await tester.drag(find.byType(DriverMapCanvas), const Offset(-80, -60));
    await tester.pump();
    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();
    await tester.tap(find.byIcon(Icons.remove));
    await tester.pump();

    expect(tester.takeException(), isNull);
  });

  testWidgets('driver map canvas uses a real street map layer', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: DriverMapCanvas(
            mapController: MapController(),
            route: DriverRouteInfo.fromApi({
              'route_name': 'GTFS Route',
              'origin': 'Stop A',
              'destination': 'Stop B',
              'current_stop_sequence': 1,
              'total_stops': 2,
              'progress_percent': 0,
              'status': 'active',
              'stops': [
                {
                  'name': 'Stop A',
                  'scheduled_time': '08:00 AM',
                  'status': 'next',
                  'sequence': 1,
                  'lat': 30.0444,
                  'lon': 31.2357,
                },
                {
                  'name': 'Stop B',
                  'scheduled_time': '08:10 AM',
                  'status': 'upcoming',
                  'sequence': 2,
                  'lat': 30.0626,
                  'lon': 31.2460,
                },
              ],
            }),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(FlutterMap), findsOneWidget);
    expect(find.byType(TileLayer), findsOneWidget);
    expect(find.byType(PolylineLayer), findsOneWidget);
    expect(find.byType(MarkerLayer), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('clicking stop completed multiple times works', (tester) async {
    tester.view.physicalSize = const Size(800, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const IzeeDriverApp());
    await tester.pumpAndSettle();

    // Sign in
    await tester.ensureVisible(find.text('Use Biometric Login'));
    await tester.tap(find.text('Use Biometric Login'));
    await tester.pumpAndSettle();

    // Start Trip first so routeState is initialized
    await tester.tap(find.text('Start Trip'));
    await tester.pumpAndSettle();

    // Tap on Route Info
    await tester.tap(find.text('Route Info'));
    await tester.pumpAndSettle();

    expect(find.text('Downtown Terminal'), findsOneWidget);
    expect(find.text('Ramses Square Stop'), findsOneWidget);

    // Click "Mark Next Stop Completed" (First Time)
    await tester.tap(find.text('Mark Next Stop Completed'));
    await tester.pumpAndSettle();

    final state = tester.state(find.byType(IzeeDriverApp)) as dynamic;
    final services = state.services as DriverServices;
    final stateVal = services.routeState.value;
    print('stateVal: $stateVal');
    print('route_id: ${stateVal?['route_id']}');
    print('mockRoutes has route_id: ${DriverServices.mockRoutes.containsKey(stateVal?['route_id'])}');

    // Go back to Home Screen
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();

    // Tap on View Map
    await tester.tap(find.text('View Map'));
    await tester.pumpAndSettle();

    // Verify map is displayed
    expect(find.text('Live Map'), findsOneWidget);

    // Go back to Home Screen
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();

    // Open drawer
    await tester.tap(find.byIcon(Icons.menu));
    await tester.pumpAndSettle();

    // Tap on My Trips
    await tester.tap(find.text('My Trips'));
    await tester.pumpAndSettle();

    // Go back to Home Screen
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();

    // Go to Route Info again
    await tester.tap(find.text('Route Info'));
    await tester.pumpAndSettle();

    // Click "Mark Next Stop Completed" (Second Time)
    await tester.tap(find.text('Mark Next Stop Completed'));
    await tester.pumpAndSettle();

    final stateVal2 = services.routeState.value;
    print('stateVal2: $stateVal2');

    expect(tester.takeException(), isNull);
  });
}
