import 'package:flutter_test/flutter_test.dart';
import 'package:izee_ui/main.dart';

void main() {
  test('route details preserve the selected alternative totals', () {
    final selectedAlternative = <String, dynamic>{
      'label': 'Fastest',
      'total_travel_time': 2460,
      'total_fare': 15,
      'transfer_count': 0,
      'legs': [
        {'mode': 'walk'},
        {'mode': 'bus', 'route_id': 'CTA_1145'},
      ],
    };
    final genericRouteDetails = <String, dynamic>{
      'route_id': 'CTA_1145',
      'total_travel_time': 6000,
      'total_fare': 100,
      'legs': [
        {'mode': 'bus', 'route_id': 'CTA_1145', 'geometry': []},
      ],
      'route_name': 'CTA 1145',
    };

    final merged = mergeSelectedRouteWithDetails(
      selectedAlternative,
      genericRouteDetails,
    );

    expect(merged['total_travel_time'], 2460);
    expect(merged['total_fare'], 15);
    expect(merged['legs'], same(selectedAlternative['legs']));
    expect(merged['route_name'], 'CTA 1145');
    expect(merged['route_id'], 'CTA_1145');
  });
}
