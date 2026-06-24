import 'package:flutter_test/flutter_test.dart';
import 'package:izee_ui/main.dart';

void main() {
  test('nearby buses include only active or freshly updated vehicles', () {
    final now = DateTime.utc(2026, 6, 22, 12);

    expect(isActiveLiveVehicle({'status': 'active'}, now: now), isTrue);
    expect(isActiveLiveVehicle({'status': 'stale'}, now: now), isFalse);
    expect(isActiveLiveVehicle({}, now: now), isFalse);
    expect(
      isActiveLiveVehicle(
        {'last_updated': now.subtract(const Duration(seconds: 30)).toIso8601String()},
        now: now,
      ),
      isTrue,
    );
    expect(
      isActiveLiveVehicle(
        {'last_updated': now.subtract(const Duration(minutes: 5)).toIso8601String()},
        now: now,
      ),
      isFalse,
    );
  });

  test('next-stop ETA is calculated beside its distance', () {
    expect(
      estimateNextStopDuration(
        distanceMeters: 840,
        locationAvailable: true,
        stepType: 'bus',
      ),
      '2 min',
    );
    expect(
      estimateNextStopDuration(
        distanceMeters: 420,
        locationAvailable: true,
        stepType: 'walk',
      ),
      '5 min',
    );
    expect(
      estimateNextStopDuration(
        distanceMeters: 0,
        locationAvailable: false,
        fallbackSeconds: 180,
      ),
      '3 min',
    );
  });
}
