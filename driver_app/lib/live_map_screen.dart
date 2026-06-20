import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'services/driver_services.dart';

class LiveMapScreen extends StatelessWidget {
  const LiveMapScreen({Key? key, required this.services}) : super(key: key);

  final DriverServices services;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Map'),
      ),
      body: ValueListenableBuilder<Map<String, dynamic>?>(
        valueListenable: services.routeState,
        builder: (context, route, _) {
          if (route == null) {
            return const Center(child: CircularProgressIndicator());
          }
          // Expect route geometry as List<List<double>> or List<Map> of lat/lon
          final geometry = route['geometry'];
          List<LatLng> points = [];
          if (geometry is List) {
            // Try to parse as list of [lat, lon] pairs
            for (var item in geometry) {
              if (item is List && item.length >= 2) {
                points.add(LatLng(item[0] as double, item[1] as double));
              } else if (item is Map) {
                final lat = item['lat'] ?? item['latitude'];
                final lon = item['lon'] ?? item['longitude'];
                if (lat != null && lon != null) {
                  points.add(LatLng(lat as double, lon as double));
                }
              }
            }
          }
          // Fallback: if no geometry, show placeholder message.
          if (points.isEmpty) {
            return const Center(child: Text('Route path not available'));
          }
          // Bounds computation removed; not needed for map display
          return FlutterMap(
            options: MapOptions(
              center: points.first,
              zoom: 13.0,
              maxZoom: 18.0,
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                subdomains: const ['a', 'b', 'c'],
              ),
              PolylineLayer(
                polylines: [
                  Polyline(
                    points: points,
                    color: Colors.blueAccent,
                    strokeWidth: 4.0,
                  ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}
