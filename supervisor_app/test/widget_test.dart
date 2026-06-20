import 'dart:async';
import 'dart:io';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:izee_supervisor/main.dart';

void main() {
  testWidgets('supervisor login opens dashboard', (tester) async {
    await tester.pumpWidget(const IzeeSupervisorApp());
    await tester.pumpAndSettle(const Duration(milliseconds: 1500));

    expect(find.text('IZEE'), findsOneWidget);
    expect(find.text('Secure Login'), findsOneWidget);
    expect(find.text('Sign In'), findsOneWidget);

    await tester.tap(find.text('Sign In'));
    await tester.pumpAndSettle();

    expect(find.text('IZEE Supervisor'), findsOneWidget);
    expect(find.text('Live Monitoring'), findsOneWidget);
    expect(find.text('Report Incident'), findsOneWidget);
    expect(find.text('Service Check'), findsOneWidget);
    expect(find.text('Control Center'), findsOneWidget);
  });

  testWidgets('profile shows supervisor logout action', (tester) async {
    await tester.pumpWidget(const IzeeSupervisorApp());
    await tester.pumpAndSettle(const Duration(milliseconds: 1500));

    await tester.tap(find.text('Sign In'));
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.person_outline).first);
    await tester.pumpAndSettle();

    expect(find.text('Profile & Settings'), findsOneWidget);

    await tester.scrollUntilVisible(
      find.text('Logout'),
      400,
      scrollable: find.byType(Scrollable).last,
    );
    expect(find.text('Logout'), findsOneWidget);
  });

  testWidgets('profile edit opens a safe prefilled modal and cancels',
      (tester) async {
    await tester.pumpWidget(const IzeeSupervisorApp());
    await tester.pumpAndSettle(const Duration(milliseconds: 1500));

    await tester.tap(find.text('Sign In'));
    await tester.pumpAndSettle();

    await tester.tap(find.byIcon(Icons.person_outline).first);
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.text('Edit Profile Information'),
      400,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.tap(find.text('Edit Profile Information'));
    await tester.pumpAndSettle();

    expect(find.byType(AlertDialog), findsOneWidget);
    expect(find.text('Edit Profile Information'), findsWidgets);
    expect(find.text('Ahmed Hassan'), findsOneWidget);
    expect(find.text('Zone East'), findsOneWidget);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(find.byType(AlertDialog), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
      'assignment edit opens modal instead of pushing a placeholder page',
      (tester) async {
    final assignment = {
      'assignment_id': 'assign_001',
      'driver_id': 'driver_test_001',
      'vehicle_id': 'BUS-4521',
      'route_id': 'BRT_PHASE1',
      'service_date': '2026-06-17',
      'start_time': '08:00:00',
      'end_time': '10:00:00',
      'status': 'scheduled',
      'notes': 'Morning duty',
    };

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Builder(
            builder: (context) => FilledButton(
              onPressed: () {
                showDialog<void>(
                  context: context,
                  builder: (_) => AssignmentEditDialog(
                    supervisorId: 'supervisor_1',
                    assignment: assignment,
                    onSave: () {},
                  ),
                );
              },
              child: const Text('Open Edit'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Open Edit'));
    await tester.pumpAndSettle();

    expect(find.byType(AlertDialog), findsOneWidget);
    expect(find.text('Edit Assignment'), findsOneWidget);
    expect(find.text('driver_test_001'), findsOneWidget);
    expect(find.text('BUS-4521'), findsOneWidget);
    expect(find.text('BRT_PHASE1'), findsOneWidget);
    expect(find.text('Morning duty'), findsOneWidget);

    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    expect(find.byType(AlertDialog), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('metric tile fits tight mobile card height', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 160,
              height: 92,
              child: MetricTile(
                icon: Icons.location_on_outlined,
                value: '8',
                label: 'Active Routes',
                color: blue,
              ),
            ),
          ),
        ),
      ),
    );

    expect(find.text('8'), findsOneWidget);
    expect(find.text('Active Routes'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('AssignmentFormScreen - Supervisor with no region shows empty state card', (tester) async {
    await HttpOverrides.runZoned(() async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AssignmentFormScreen(
              supervisorId: 'supervisor_no_region',
              onSave: _dummyCallback,
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));

      expect(find.text('No active region assigned'), findsOneWidget);
      expect(find.text('Please contact Control Center to assign you to a region before creating assignments.'), findsOneWidget);
      
      // Verify dropdowns are disabled
      final driverDropdown = tester.widget<DropdownButtonFormField<String>>(
        find.byType(DropdownButtonFormField<String>).first,
      );
      expect(driverDropdown.onChanged, isNull);

      final button = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Complete region setup first.'),
      );
      expect(button.onPressed, isNull);
    }, createHttpClient: (context) {
      return FakeHttpClient({
        '/supervisor/supervisor_no_region/region': '{"detail": "Not found"}',
      }, statusCodes: {
        '/supervisor/supervisor_no_region/region': 404,
      });
    });
  });

  testWidgets('AssignmentFormScreen - Supervisor with region but no vehicles shows empty message', (tester) async {
    await HttpOverrides.runZoned(() async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AssignmentFormScreen(
              supervisorId: 'supervisor_no_vehicles',
              onSave: _dummyCallback,
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));
      expect(find.text("No vehicles assigned to this region."), findsOneWidget);
      
      final button = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Complete region setup first.'),
      );
      expect(button.onPressed, isNull);
    }, createHttpClient: (context) {
      return FakeHttpClient({
        '/supervisor/supervisor_no_vehicles/region': '{"region_id": "Zone_Vehicles_Empty", "region_name": "Zone Vehicles Empty"}',
        '/regions/Zone_Vehicles_Empty/routes': '[{"route_id": "Route_1"}]',
        '/regions/Zone_Vehicles_Empty/vehicles': '[]',
        '/regions/Zone_Vehicles_Empty/drivers': '[{"driver_id": "driver_1"}]',
      });
    });
  });

  testWidgets('AssignmentFormScreen - Supervisor with region but no routes shows empty message', (tester) async {
    await HttpOverrides.runZoned(() async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AssignmentFormScreen(
              supervisorId: 'supervisor_no_routes',
              onSave: _dummyCallback,
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));

      expect(find.text("No bus routes assigned to this region."), findsOneWidget);
      
      final button = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Complete region setup first.'),
      );
      expect(button.onPressed, isNull);
    }, createHttpClient: (context) {
      return FakeHttpClient({
        '/supervisor/supervisor_no_routes/region': '{"region_id": "Zone_Routes_Empty", "region_name": "Zone Routes Empty"}',
        '/regions/Zone_Routes_Empty/routes': '[]',
        '/regions/Zone_Routes_Empty/vehicles': '[{"vehicle_id": "BUS_001"}]',
        '/regions/Zone_Routes_Empty/drivers': '[{"driver_id": "driver_1"}]',
      });
    });
  });

  testWidgets('AssignmentFormScreen - Complete setup works', (tester) async {
    await HttpOverrides.runZoned(() async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AssignmentFormScreen(
              supervisorId: 'supervisor_valid',
              onSave: _dummyCallback,
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(seconds: 1));

      expect(find.text("No active region assigned"), findsNothing);
      expect(find.text("No vehicles assigned to this region."), findsNothing);
      expect(find.text("No bus routes assigned to this region."), findsNothing);
      
      final button = tester.widget<FilledButton>(
        find.widgetWithText(FilledButton, 'Create Assignment'),
      );
      expect(button.onPressed, isNotNull);
    }, createHttpClient: (context) {
      return FakeHttpClient({
        '/supervisor/supervisor_valid/region': '{"region_id": "Zone_Valid", "region_name": "Zone Valid"}',
        '/regions/Zone_Valid/routes': '[{"route_id": "Route_1"}]',
        '/regions/Zone_Valid/vehicles': '[{"vehicle_id": "BUS_001"}]',
        '/regions/Zone_Valid/drivers': '[{"driver_id": "driver_1"}]',
      });
    });
  });
}

class FakeHttpClient extends Fake implements HttpClient {
  FakeHttpClient(this.responses, {this.statusCodes = const {}});
  final Map<String, String> responses;
  final Map<String, int> statusCodes;

  @override
  Future<HttpClientRequest> openUrl(String method, Uri url) async {
    return FakeHttpClientRequest(url.toString(), responses, statusCodes);
  }

  @override
  void close({bool force = false}) {}
}

class FakeHttpClientRequest extends Fake implements HttpClientRequest {
  FakeHttpClientRequest(this.url, this.responses, this.statusCodes);
  final String url;
  final Map<String, String> responses;
  final Map<String, int> statusCodes;

  @override
  final HttpHeaders headers = FakeHttpHeaders();

  @override
  bool followRedirects = true;

  @override
  int maxRedirects = 5;

  @override
  bool persistentConnection = true;

  @override
  int contentLength = 0;

  @override
  void write(Object? obj) {}

  @override
  void add(List<int> data) {}

  @override
  Future<void> addStream(Stream<List<int>> stream) async {}

  @override
  Future<HttpClientResponse> close() async {
    String matchedKey = '';
    for (final key in responses.keys) {
      if (url.contains(key)) {
        matchedKey = key;
        break;
      }
    }
    if (matchedKey.isNotEmpty) {
      final code = statusCodes[matchedKey] ?? 200;
      return FakeHttpClientResponse(responses[matchedKey]!, code);
    }
    return FakeHttpClientResponse('{"detail": "Not Found"}', 404);
  }
}

class FakeHttpHeaders extends Fake implements HttpHeaders {
  @override
  void add(String name, Object value, {bool preserveHeaderCase = false}) {}
  @override
  void set(String name, Object value, {bool preserveHeaderCase = false}) {}
  @override
  List<String>? operator [](String name) => null;
  @override
  void forEach(void Function(String name, List<String> values) action) {}
}

class FakeHttpClientResponse extends Fake implements HttpClientResponse {
  FakeHttpClientResponse(this.body, this.statusCode);
  final String body;
  final int statusCode;

  @override
  int get contentLength => body.length;

  @override
  final HttpHeaders headers = FakeHttpHeaders();

  @override
  String get reasonPhrase => '';

  @override
  bool get isRedirect => false;

  @override
  bool get persistentConnection => true;

  @override
  List<RedirectInfo> get redirects => const [];

  @override
  StreamSubscription<List<int>> listen(
    void Function(List<int> event)? onData, {
    Function? onError,
    void Function()? onDone,
    bool? cancelOnError,
  }) {
    final bytes = utf8.encode(body);
    return Stream<List<int>>.fromIterable([bytes]).listen(
      onData,
      onError: onError,
      onDone: onDone,
      cancelOnError: cancelOnError,
    );
  }
}

void _dummyCallback() {}
