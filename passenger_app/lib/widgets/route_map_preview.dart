// File: lib/widgets/route_map_preview.dart
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

/// A map preview that displays the selected route (if provided) and live vehicle
/// markers. It logs debugging information required by the user.
class RouteMapPreview extends StatelessWidget {
  const RouteMapPreview({
    super.key,
    required this.route,
    required this.liveVehicles,
  });

  /// The route data, may contain an identifier and geometry. Can be null.
  final Map<String, dynamic>? route;

  /// List of live vehicle objects received from the backend. Expected fields:
  ///   - 'vehicle_id' (String)
  ///   - 'lat' (num or String)
  ///   - 'lon' (num or String)
  final List<Map<String, dynamic>> liveVehicles;

  @override
  Widget build(BuildContext context) {
    // Log the selected route id (if any)
    final selectedRouteId = route != null ? route!['route_id']?.toString() : null;
    // ignore: avoid_print
    print('PASSENGER_SELECTED_ROUTE_ID: $selectedRouteId');

    // Log receipt of live vehicles
    // ignore: avoid_print
    print('LIVE_VEHICLES_RECEIVED: ${liveVehicles.length}');

    // Build markers from liveVehicles with valid lat/lng
    final markers = <Marker>[];
    for (final vehicle in liveVehicles) {
      final lat = _asDouble(vehicle['lat']);
      final lon = _asDouble(vehicle['lon']);
      // ignore: avoid_print
      print('MARKER_LAT: $lat');
      // ignore: avoid_print
      print('MARKER_LNG: $lon');
      if (lat == null || lon == null) continue;
      markers.add(
          Marker(
            width: 40,
            height: 40,
            point: LatLng(lat, lon),
            child: const Icon(Icons.directions_bus, color: Colors.blue, size: 30),
          ),
      );
    }
    // Log marker counts
    // ignore: avoid_print
    print('MARKERS_CREATED_COUNT: ${markers.length}');

    // Determine initial map centre. Use first marker if exists, else a default location.
    final center = markers.isNotEmpty
        ? markers.first.point
        : const LatLng(0.0, 0.0);

    return FlutterMap(
      options: MapOptions(
        center: center,
        zoom: 14,
        // Disable interactive gestures that might interfere with UI layout
        interactiveFlags: InteractiveFlag.all,
      ),
      children: [
        TileLayer(
          urlTemplate:
              'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
          subdomains: const ['a', 'b', 'c'],
          userAgentPackageName: 'com.izee.passenger',
        ),
        if (markers.isNotEmpty)
          MarkerLayer(markers: markers),
        // Log rendering count after Flutter builds the widget tree
        // ignore: avoid_print
        Builder(builder: (_) {
          // ignore: avoid_print
          print('MARKERS_RENDERED_COUNT: ${markers.length}');
          return const SizedBox.shrink();
        }),
      ],
    );
  }

  double? _asDouble(Object? value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    return double.tryParse(value.toString());
  }
}
