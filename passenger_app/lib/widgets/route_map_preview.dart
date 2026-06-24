// File: lib/widgets/route_map_preview.dart
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

class _UserLocationMarker extends StatelessWidget {
  const _UserLocationMarker({super.key, this.heading});
  final double? heading;

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        // Pulsing outer blue ring
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.blue.withValues(alpha: 0.15),
          ),
        ),
        // White border ring
        Container(
          width: 18,
          height: 18,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.white,
            boxShadow: [
              BoxShadow(
                color: Colors.black26,
                blurRadius: 4,
                offset: Offset(0, 2),
              ),
            ],
          ),
        ),
        // Blue center dot
        Container(
          width: 12,
          height: 12,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.blue,
          ),
        ),
        // Directional cone showing heading
        if (heading != null)
          Transform.rotate(
            angle: (heading! * math.pi) / 180,
            child: CustomPaint(
              size: const Size(36, 36),
              painter: _DirectionConePainter(),
            ),
          ),
      ],
    );
  }
}

class _DirectionConePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..shader = RadialGradient(
        colors: [
          Colors.blue.withValues(alpha: 0.4),
          Colors.blue.withValues(alpha: 0.0),
        ],
      ).createShader(Rect.fromCircle(
          center: Offset(size.width / 2, size.height / 2),
          radius: size.width / 2))
      ..style = PaintingStyle.fill;

    final path = ui.Path()
      ..moveTo(size.width / 2, size.height / 2)
      ..arcTo(
        Rect.fromCircle(
            center: Offset(size.width / 2, size.height / 2),
            radius: size.width / 2),
        -math.pi / 2 - math.pi / 6, // 30 degrees left of straight up
        math.pi / 3, // 60 degrees spread
        false,
      )
      ..close();

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// A map preview that displays the selected route (if provided) and live vehicle
/// markers. It logs debugging information required by the user.
class RouteMapPreview extends StatelessWidget {
  const RouteMapPreview({
    key,
    required this.route,
    this.liveVehicles = const [],
    this.userLocation,
    this.userHeading,
    this.mapController,
    this.onPositionChanged,
  }) : super(key: key);

  /// The route data, may contain an identifier and geometry. Can be null.
  final Map<String, dynamic>? route;

  /// List of live vehicle objects received from the backend. Expected fields:
  ///   - 'vehicle_id' (String)
  ///   - 'lat' (num or String)
  ///   - 'lon' (num or String)
  final List<Map<String, dynamic>> liveVehicles;

  /// Optional coordinates for user's real-time position
  final LatLng? userLocation;

  /// Optional heading/bearing for user
  final double? userHeading;

  /// Optional controller to manipulate map state (move/zoom)
  final MapController? mapController;

  /// Callback for map position changes (e.g. user drags the map)
  final void Function(MapPosition, bool)? onPositionChanged;

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
    final vehicleMarkers = <Marker>[];
    for (final vehicle in liveVehicles) {
      final lat = _asDouble(vehicle['lat']);
      final lon = _asDouble(vehicle['lon']);
      // ignore: avoid_print
      print('MARKER_LAT: $lat');
      // ignore: avoid_print
      print('MARKER_LNG: $lon');
      if (lat == null || lon == null) continue;
      vehicleMarkers.add(
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
    print('MARKERS_CREATED_COUNT: ${vehicleMarkers.length}');

    // Determine initial map centre. Use user location, first marker, or default.
    final center = userLocation ?? (vehicleMarkers.isNotEmpty
        ? vehicleMarkers.first.point
        : const LatLng(0.0, 0.0));

    return FlutterMap(
      mapController: mapController,
      options: MapOptions(
        initialCenter: center,
        initialZoom: 14,
        interactionOptions: const InteractionOptions(
          flags: InteractiveFlag.all,
        ),
        onPositionChanged: onPositionChanged,
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
          subdomains: const ['a', 'b', 'c'],
          userAgentPackageName: 'com.izee.passenger',
        ),
        MarkerLayer(
          markers: [
            if (userLocation != null)
              Marker(
                point: userLocation!,
                width: 48,
                height: 48,
                child: _UserLocationMarker(heading: userHeading),
              ),
            ...vehicleMarkers,
          ],
        ),
        // Log rendering count after Flutter builds the widget tree
        // ignore: avoid_print
        Builder(builder: (_) {
          // ignore: avoid_print
          print('MARKERS_RENDERED_COUNT: ${vehicleMarkers.length}');
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
