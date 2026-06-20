import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const IzeeDriverApp());
}

class IzeeDriverApp extends StatelessWidget {
  const IzeeDriverApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'IZEE Driver GPS',
      theme: ThemeData(useMaterial3: true),
      home: const GpsSenderPage(),
    );
  }
}

class GpsSenderPage extends StatefulWidget {
  const GpsSenderPage({super.key});

  @override
  State<GpsSenderPage> createState() => _GpsSenderPageState();
}

class _GpsSenderPageState extends State<GpsSenderPage> {
  static const Duration sendInterval = Duration(seconds: 10);

  String status = 'Trip not started';
  bool sending = false;
  bool tripActive = false;
  int sentCount = 0;
  Timer? locationTimer;

  final String apiUrl = 'http://127.0.0.1:8000/vehicle/location';

  Future<bool> ensureLocationReady() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      setState(() {
        status = 'Location service is disabled';
      });
      return false;
    }

    LocationPermission permission = await Geolocator.checkPermission();

    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      setState(() {
        status = 'Location permission denied';
      });
      return false;
    }

    return true;
  }

  Future<void> startTrip() async {
    final ready = await ensureLocationReady();
    if (!ready) {
      return;
    }

    setState(() {
      tripActive = true;
      sentCount = 0;
      status = 'Trip started. Sending location...';
    });

    await sendLocation();

    locationTimer?.cancel();
    locationTimer = Timer.periodic(sendInterval, (_) {
      sendLocation();
    });
  }

  void endTrip() {
    locationTimer?.cancel();
    locationTimer = null;

    setState(() {
      tripActive = false;
      sending = false;
      status = 'Trip ended. Sent $sentCount location updates.';
    });
  }

  Future<void> sendLocation() async {
    if (sending) {
      return;
    }

    setState(() {
      sending = true;
      status = 'Getting GPS...';
    });

    try {
      final ready = await ensureLocationReady();
      if (!ready) {
        if (tripActive) {
          endTrip();
        } else {
          setState(() {
            sending = false;
          });
        }
        return;
      }

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      final payload = {
        'vehicle_id': 'driver_test_001',
        'timestamp': DateTime.now().toUtc().toIso8601String(),
        'location': {
          'lat': position.latitude,
          'lon': position.longitude,
        },
        'speed': position.speed < 0 ? null : position.speed,
        'bearing': position.heading < 0 ? null : position.heading,
      };

      final response = await http.post(
        Uri.parse(apiUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );

      setState(() {
        sentCount += 1;
        status =
            'Sent $sentCount update(s)\nHTTP ${response.statusCode}: ${response.body}';
        sending = false;
      });
    } catch (e) {
      setState(() {
        status = 'Error: $e';
        sending = false;
      });
    }
  }

  @override
  void dispose() {
    locationTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('IZEE Driver GPS'),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              FilledButton(
                onPressed: tripActive ? null : startTrip,
                child: const Text('Start Trip'),
              ),
              const SizedBox(height: 12),
              FilledButton.tonal(
                onPressed: tripActive ? endTrip : null,
                child: const Text('End Trip'),
              ),
              const SizedBox(height: 24),
              Text(
                tripActive
                    ? 'Trip running. Sending every ${sendInterval.inSeconds} seconds.'
                    : 'Trip stopped.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                status,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
