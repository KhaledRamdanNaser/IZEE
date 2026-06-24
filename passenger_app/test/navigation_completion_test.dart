import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:izee_ui/main.dart';

void main() {
  testWidgets('finishing the final navigation step closes with reached result',
      (tester) async {
    bool? destinationReached;
    final route = <String, dynamic>{
      'total_travel_time': 300,
      'navigation_steps': [
        {
          'instruction': 'Arrive at destination',
          'type': 'walk',
          'target_stop': {
            'stop_id': 'destination',
            'name': 'Destination',
            'lat': 30.0444,
            'lon': 31.2357,
          },
        },
      ],
      'legs': [
        {
          'mode': 'walk',
          'from_stop': {
            'stop_id': 'origin',
            'name': 'Origin',
            'lat': 30.0450,
            'lon': 31.2350,
          },
          'to_stop': {
            'stop_id': 'destination',
            'name': 'Destination',
            'lat': 30.0444,
            'lon': 31.2357,
          },
        },
      ],
    };

    await tester.pumpWidget(MaterialApp(
      home: Builder(builder: (context) {
        return TextButton(
          onPressed: () async {
            destinationReached = await Navigator.push<bool>(
              context,
              MaterialPageRoute(
                builder: (_) => NavigationScreen(selectedRoute: route),
              ),
            );
          },
          child: const Text('Open navigation'),
        );
      }),
    ));

    await tester.tap(find.text('Open navigation'));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationScreen), findsOneWidget);

    await tester.tap(find.byTooltip('Skip Step (Debug)'));
    await tester.pumpAndSettle();

    expect(find.byType(NavigationScreen), findsNothing);
    expect(destinationReached, isTrue);
  });
}
