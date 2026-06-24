import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_service.dart';

class DriverTripState {
  const DriverTripState({
    required this.active,
    required this.sending,
    required this.vehicleId,
    required this.routeId,
    this.lastPosition,
    this.lastSentAt,
    this.lastError,
    this.queuedCount = 0,
    this.tripStartedAt,
    this.assignmentId,
    this.driverId,
    this.tripId,
    this.regionId,
  });

  const DriverTripState.initial()
      : active = false,
        sending = false,
        vehicleId = 'driver_test_001',
        routeId = '',
        lastPosition = null,
        lastSentAt = null,
        lastError = null,
        queuedCount = 0,
        tripStartedAt = null,
        assignmentId = null,
        driverId = 'driver_test_001',
        tripId = null,
        regionId = null;

  final bool active;
  final bool sending;
  final String vehicleId;
  final String routeId;
  final Position? lastPosition;
  final DateTime? lastSentAt;
  final String? lastError;
  final int queuedCount;
  /// UTC timestamp of when the current trip was started.
  final DateTime? tripStartedAt;
  final String? assignmentId;
  final String? driverId;
  final String? tripId;
  final String? regionId;

  DriverTripState copyWith({
    bool? active,
    bool? sending,
    String? vehicleId,
    String? routeId,
    Position? lastPosition,
    DateTime? lastSentAt,
    String? lastError,
    bool clearError = false,
    int? queuedCount,
    DateTime? tripStartedAt,
    bool clearTripStart = false,
    String? assignmentId,
    bool clearAssignment = false,
    String? driverId,
    String? tripId,
    bool clearTripId = false,
    String? regionId,
    bool clearRegionId = false,
  }) {
    return DriverTripState(
      active: active ?? this.active,
      sending: sending ?? this.sending,
      vehicleId: vehicleId ?? this.vehicleId,
      routeId: routeId ?? this.routeId,
      lastPosition: lastPosition ?? this.lastPosition,
      lastSentAt: lastSentAt ?? this.lastSentAt,
      lastError: clearError ? null : lastError ?? this.lastError,
      queuedCount: queuedCount ?? this.queuedCount,
      tripStartedAt: clearTripStart ? null : tripStartedAt ?? this.tripStartedAt,
      assignmentId: clearAssignment ? null : assignmentId ?? this.assignmentId,
      driverId: driverId ?? this.driverId,
      tripId: clearTripId ? null : tripId ?? this.tripId,
      regionId: clearRegionId ? null : regionId ?? this.regionId,
    );
  }
}

class DriverServices {
  DriverServices({ApiService? api}) : api = api ?? ApiService() {
    _startMessagePolling();
    initSettings();
  }

  void _startMessagePolling() {
    _messageRefreshTimer?.cancel();
    _messageRefreshTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      loadUnreadCount();
    });
  }

  static const defaultVehicleId = 'driver_test_001';
  static const defaultRouteId = 'A-12 Express';

  final ApiService api;
  final ValueNotifier<DriverTripState> tripState =
      ValueNotifier<DriverTripState>(const DriverTripState.initial());
  final ValueNotifier<Map<String, dynamic>?> routeState =
      ValueNotifier<Map<String, dynamic>?>(null);
  /// Live count of unread messages — drives the badge on the Messages tile.
  final ValueNotifier<int> unreadCount = ValueNotifier<int>(0);
  final ValueNotifier<Map<String, dynamic>> appSettings =
      ValueNotifier<Map<String, dynamic>>(const {
    'language': 'en',
    'theme': 'system',
    'notificationsEnabled': true,
    'locationUpdateInterval': 10,
    'autoSendLocation': true,
    'keepScreenAwake': true,
    'showStopAdvancement': true,
  });
  final List<Map<String, dynamic>> _queuedObservations = [];

  List<Map<String, dynamic>>? _cachedMessages;
  bool _hasInitializedMessages = false;

  Timer? _locationTimer;
  Timer? _messageRefreshTimer;
  WebSocket? _messageSocket;
  Timer? _messageSocketPingTimer;
  bool _sendingTick = false;
  String _driverId = defaultDriverId;
  String _vehicleId = defaultVehicleId;
  String _activeRouteId = defaultRouteId;
  bool _mockHistoryCleared = false;

  static const mockRoutes = <String, Map<String, dynamic>>{};
  static const defaultDriverId = 'driver_test_001';

  Future<Map<String, dynamic>> login({
    required String driverId,
    required String password,
  }) async {
    final normalizedDriverId = driverId.trim();
    _driverId = normalizedDriverId.isEmpty ? defaultDriverId : normalizedDriverId;
    tripState.value = tripState.value.copyWith(
      driverId: _driverId,
      vehicleId: _vehicleId,
      clearError: true,
    );
    // Presence is optional infrastructure. Never make a socket handshake block
    // a successful Driver App login.
    unawaited(_connectMessageSocket(
        _driverId));
    return {
      'status': 'local_login',
      'driver_id': _driverId,
    };
  }

  Future<void> _connectMessageSocket(String driverId) async {
    try {
      await _messageSocket?.close();
      _messageSocketPingTimer?.cancel();
      final wsBase = ApiConfig.baseUrl.replaceFirst(RegExp(r'^http'), 'ws');
      _messageSocket = await WebSocket.connect(
              '$wsBase/ws/messages?user_type=driver&user_id=${Uri.encodeQueryComponent(driverId)}')
          .timeout(const Duration(seconds: 5));
      _messageSocketPingTimer = Timer.periodic(const Duration(seconds: 15), (timer) {
        if (_messageSocket == null) return timer.cancel();
        _messageSocket!.add('ping');
      });
    } catch (_) {}
  }

  Future<void> startTrip() async {
    await _ensureLocationReady();
    _locationTimer?.cancel();

    final autoSend = appSettings.value['autoSendLocation'] == true;
    tripState.value = tripState.value.copyWith(
      active: true,
      sending: autoSend,
      clearError: true,
      tripStartedAt: DateTime.now().toUtc(),
    );

    if (autoSend) {
      await _sendCurrentLocation();
      final interval = appSettings.value['locationUpdateInterval'] as int? ?? 10;
      _locationTimer =
          Timer.periodic(Duration(seconds: interval), (_) => _sendCurrentLocation());
    }

    try {
      await loadRouteInfo();
    } catch (_) {
      // Ignored, loadRouteInfo handles fallback
    }
  }

  Future<void> endTrip({bool completeBackend = true}) async {
    final activeAssignmentId = tripState.value.assignmentId;
    if (completeBackend && activeAssignmentId != null) {
      try {
        if (!activeAssignmentId.startsWith('mock_')) {
          await api.completeAssignment(assignmentId: activeAssignmentId);
        }
      } catch (e) {
        debugPrint('IZEE Driver API: Failed to complete assignment during endTrip: $e');
      }
    }

    _locationTimer?.cancel();
    _locationTimer = null;

    if (_queuedObservations.isNotEmpty) {
      _queuedObservations.clear();
      debugPrint('DRIVER_LOCATION_QUEUE_CLEARED_ON_TRIP_END');
    }

    tripState.value = tripState.value.copyWith(
      active: false,
      sending: false,
      clearError: true,
      queuedCount: _queuedObservations.length,
      clearTripStart: true,
      clearAssignment: true,
      clearTripId: true,
      clearRegionId: true,
    );

    routeState.value = null;
  }

  Future<void> sendOneLocationNow() async {
    await _ensureLocationReady();
    await _sendCurrentLocation();
  }

  Future<Map<String, dynamic>> submitIncidentReport({
    required String category,
    required String details,
    String recipient = 'Supervisor',
  }) async {
    await _ensureLocationReady();
    final position = await Geolocator.getCurrentPosition(
      desiredAccuracy: LocationAccuracy.high,
    );
    final state = tripState.value;
    final incident = {
      'category': category,
      'severity': _severityForCategory(category),
      'status': 'new',
      'recipient': recipient,
      'vehicle_id': _vehicleId,
      'route_id': state.routeId,
      'details': details.trim().isEmpty ? null : details.trim(),
      'location': {
        'lat': position.latitude,
        'lon': position.longitude,
      },
      'location_label':
          '${position.latitude.toStringAsFixed(5)}, ${position.longitude.toStringAsFixed(5)}',
      'speed': position.speed.isFinite && position.speed >= 0
          ? position.speed
          : null,
      'bearing': position.heading.isFinite && position.heading >= 0
          ? position.heading
          : null,
      'source': 'driver_app',
      'created_at': DateTime.now().toUtc().toIso8601String(),
    };

    return api.createIncident(incident: incident);
  }

  void _initializeFallbackMessages() {
    _cachedMessages = [
      {
        'message_id': 'fallback_1',
        'sender': 'Control Center',
        'subject': 'Route Change Alert',
        'body': 'Due to roadwork on Main St, please use alternate route via Bridge Rd.',
        'created_at': DateTime.now().subtract(const Duration(minutes: 10)).toUtc().toIso8601String(),
        'read': false,
        'priority': 'urgent',
      },
      {
        'message_id': 'fallback_2',
        'sender': 'Supervisor',
        'subject': 'Passenger Count Request',
        'body': 'Please confirm current passenger count at next stop.',
        'created_at': DateTime.now().subtract(const Duration(minutes: 25)).toUtc().toIso8601String(),
        'read': false,
        'priority': 'normal',
      },
      {
        'message_id': 'fallback_3',
        'sender': 'Supervisor',
        'subject': 'Weather Advisory',
        'body': 'Rain expected in 30 mins. Please drive with extra caution.',
        'created_at': DateTime.now().subtract(const Duration(hours: 1)).toUtc().toIso8601String(),
        'read': false,
        'priority': 'normal',
      },
    ];
    _hasInitializedMessages = true;
    _updateUnreadCount();
  }

  void _updateUnreadCount() {
    if (_cachedMessages != null) {
      unreadCount.value = _cachedMessages!.where((m) => m['read'] != true).length;
    }
  }

  List<Map<String, dynamic>> getCachedMessages() {
    if (!_hasInitializedMessages) {
      _initializeFallbackMessages();
    }
    return _cachedMessages!;
  }

  Future<void> markAllAsRead() async {
    if (!_hasInitializedMessages) {
      _initializeFallbackMessages();
    }
    for (var msg in _cachedMessages!) {
      if (msg['read'] != true) {
        msg['read'] = true;
        final id = msg['message_id']?.toString() ?? '';
        if (id.isNotEmpty && !id.startsWith('fallback_')) {
          try {
            await api.markMessageRead(id);
          } catch (_) {}
        }
      }
    }
    _updateUnreadCount();
  }

  Future<List<Map<String, dynamic>>> loadMessages() async {
    try {
      final response = await api.getMessages(recipientId: _driverId);
      final messages = response['messages'];
      if (messages is List) {
        final list = messages.whereType<Map<String, dynamic>>().map((m) {
          return Map<String, dynamic>.from(m);
        }).toList();
        debugPrint('IZEE Driver API: Loaded messages from live backend API');
        _cachedMessages = list;
        _hasInitializedMessages = true;
        _updateUnreadCount();
        return _cachedMessages!;
      }
      _cachedMessages = const [];
      _updateUnreadCount();
      return const [];
    } catch (error) {
      // API unreachable / failed
      debugPrint('IZEE Driver API: Failed to connect to live backend, using local/mock repository layer');
      if (!_hasInitializedMessages) {
        _initializeFallbackMessages();
      }
      rethrow;
    }
  }

  /// Fetches messages silently to refresh [unreadCount] without returning data.
  Future<void> loadUnreadCount() async {
    try {
      await loadMessages();
    } catch (_) {
      // Error already handled or fallback count applied in _initializeFallbackMessages on catch.
    }
  }

  /// Call this after the driver has viewed the messages screen to clear the badge.
  void clearUnreadBadge() {
    unreadCount.value = 0;
  }

  Future<void> markMessageRead(String messageId) async {
    if (_cachedMessages != null) {
      for (var msg in _cachedMessages!) {
        if (msg['message_id'] == messageId) {
          msg['read'] = true;
        }
      }
      _updateUnreadCount();
    }

    if (!messageId.startsWith('fallback_')) {
      try {
        await api.markMessageRead(messageId);
      } catch (_) {}
    }
  }

  Future<List<Map<String, dynamic>>> loadAssignedDuties() async {
    try {
      debugPrint('AUTH_DRIVER_ID: $_driverId');
      debugPrint('MY_TRIPS_REQUEST: driver_id=$_driverId');
      final response = await api.getDriverAssignments(driverId: _driverId);
      debugPrint('MY_TRIPS_RESPONSE: $response');
      final list = response['assigned_trips'] ?? response['assignments'];
      if (list is List) {
        debugPrint('IZEE Driver API: Loaded assignments from live backend duties API');
        return list.whereType<Map<String, dynamic>>().toList(growable: false);
      }
    } catch (e) {
      debugPrint('IZEE Driver API: Failed to connect to live backend assignments API, using local mock repository fallback. Error: $e');
    }

    return const [];
  }

  Future<void> startAssignment({
    required String assignmentId,
    required String routeId,
    String? tripId,
    String? vehicleId,
  }) async {
    Map<String, dynamic>? startedAssignment;
    try {
      if (!assignmentId.startsWith('mock_')) {
        debugPrint(
            'START_TRIP_REQUEST: assignment_id=$assignmentId driver_id=$_driverId');
        final response =
            await api.startAssignment(assignmentId: assignmentId, driverId: _driverId);
        debugPrint('START_TRIP_RESPONSE: $response');
        final assignment = response['assignment'];
        if (assignment is Map<String, dynamic>) {
          startedAssignment = assignment;
        } else {
          startedAssignment = response;
        }
        debugPrint('IZEE Driver API: Started assignment $assignmentId on live backend API');
      } else {
        debugPrint('IZEE Driver API: Started assignment $assignmentId locally (mock)');
        // Retrieve mock assignment details from the fallback list
        final mockAssignments = await loadAssignedDuties();
        final mock = mockAssignments.firstWhere(
            (a) => a['assignment_id'] == assignmentId,
            orElse: () => {});
        if (mock.isNotEmpty) {
          startedAssignment = mock;
        }
      }
    } catch (e) {
      debugPrint('IZEE Driver API: startAssignment API failed: $e');
      rethrow;
    }

    final selectedRouteId =
        startedAssignment?['route_id']?.toString() ?? routeId;
    final selectedVehicleId = startedAssignment?['vehicle_id']?.toString() ?? (assignmentId.startsWith('mock_') ? null : vehicleId) ?? _vehicleId;
    final selectedTripId = startedAssignment?['trip_id']?.toString() ?? tripId;
    final selectedDriverId =
        startedAssignment?['driver_id']?.toString() ?? _driverId;
    final selectedRegionId = startedAssignment?['region_id']?.toString();

    _activeRouteId = selectedRouteId;
    routeState.value = null;
    
    await _ensureLocationReady();
    _locationTimer?.cancel();
    final autoSend = appSettings.value['autoSendLocation'] == true;
    tripState.value = tripState.value.copyWith(
      active: true,
      sending: autoSend,
      vehicleId: selectedVehicleId,
      routeId: selectedRouteId,
      assignmentId: assignmentId,
      driverId: selectedDriverId,
      tripId: selectedTripId,
      regionId: selectedRegionId,
      clearError: true,
      tripStartedAt: DateTime.now().toUtc(),
    );
    debugPrint('DRIVER_START_TRIP_SUCCESS');
    debugPrint('ACTIVE_ASSIGNMENT_ID: ${tripState.value.assignmentId}');
    debugPrint('ACTIVE_TRIP_ID: ${tripState.value.tripId}');
    debugPrint('ACTIVE_DRIVER_ID: ${tripState.value.driverId}');
    debugPrint('ACTIVE_VEHICLE_ID: ${tripState.value.vehicleId}');
    debugPrint('ACTIVE_ROUTE_ID: ${tripState.value.routeId}');
    debugPrint(
        'MAP_NAVIGATION_ARGUMENTS: assignment_id=$assignmentId trip_id=$selectedTripId route_id=$selectedRouteId vehicle_id=$selectedVehicleId driver_id=$selectedDriverId');

    if (autoSend) {
      debugPrint('DRIVER_LOCATION_STREAM_STARTED');
      await _sendCurrentLocation();
      final interval = appSettings.value['locationUpdateInterval'] as int? ?? 10;
      _locationTimer = Timer.periodic(Duration(seconds: interval), (_) => _sendCurrentLocation());
    }

    try {
      await loadRouteInfo();
    } catch (_) {}
  }

  Future<void> completeAssignment({
    required String assignmentId,
  }) async {
    try {
      if (!assignmentId.startsWith('mock_')) {
        await api.completeAssignment(assignmentId: assignmentId);
        debugPrint('IZEE Driver API: Completed assignment $assignmentId on live backend API');
      } else {
        debugPrint('IZEE Driver API: Completed assignment $assignmentId locally (mock)');
      }
    } catch (e) {
      debugPrint('IZEE Driver API: completeAssignment API failed: $e');
    }

    await endTrip(completeBackend: false);

    tripState.value = tripState.value.copyWith(
      clearAssignment: true,
      clearTripId: true,
    );
  }

  Future<void> clearTripHistory() async {
    _mockHistoryCleared = true;
    if (_driverId.isNotEmpty && !_driverId.startsWith('mock_')) {
      await api.clearDriverTripHistory(driverId: _driverId);
    }
  }

  Future<List<Map<String, dynamic>>> loadTripHistory() async {
    if (_mockHistoryCleared) {
      return const <Map<String, dynamic>>[];
    }
    try {
      final response = await api.getDriverTripHistory(driverId: _driverId);
      final history = response['history'];
      if (history is List) {
        debugPrint('IZEE Driver API: Loaded trip history from live backend API');
        return history.whereType<Map<String, dynamic>>().toList(growable: false);
      }
    } catch (_) {
      // Offline/demo fallback below.
    }

    debugPrint('IZEE Driver API: Failed to connect to live backend, using local/mock repository layer');
    return [
      {
        'trip_id': 'T-8801',
        'route_id': 'A-12 Express',
        'route_name': 'A-12 Express',
        'origin': 'Downtown Terminal',
        'destination': 'Cairo Stadium',
        'start_time': '08:15 AM',
        'end_time': '08:55 AM',
        'duration': '40m',
        'status': 'completed',
      },
      {
        'trip_id': 'T-8802',
        'route_id': 'B-20 Local',
        'route_name': 'B-20 Local',
        'origin': 'Giza Square Terminal',
        'destination': 'Heliopolis Gate',
        'start_time': '11:00 AM',
        'end_time': '12:05 PM',
        'duration': '1h 5m',
        'status': 'completed',
      },
      {
        'trip_id': 'T-8803',
        'route_id': 'A-12 Express',
        'route_name': 'A-12 Express',
        'origin': 'Downtown Terminal',
        'destination': 'Cairo Stadium',
        'start_time': '01:30 PM',
        'end_time': '01:45 PM',
        'duration': '15m',
        'status': 'cancelled',
      },
      {
        'trip_id': 'T-8804',
        'route_id': 'C-05 Shuttle',
        'route_name': 'C-05 Shuttle',
        'origin': 'Maadi Ring Road',
        'destination': 'New Cairo Hub',
        'start_time': '03:15 PM',
        'end_time': '03:50 PM',
        'duration': '35m',
        'status': 'interrupted',
      },
    ];
  }

  Future<void> switchActiveTrip(String newRouteId) async {
    _activeRouteId = newRouteId;
    tripState.value = tripState.value.copyWith(
      routeId: newRouteId,
      clearError: true,
    );

    try {
      final response = await api.getDriverRouteInfo(
        vehicleId: _vehicleId,
        routeId: newRouteId,
      );
      final route = response['route'];
      if (route is Map<String, dynamic>) {
        routeState.value = route;
        _activeRouteId = route['route_id']?.toString() ?? newRouteId;
        tripState.value = tripState.value.copyWith(
          routeId: _activeRouteId,
          clearError: true,
        );
        return;
      }
    } catch (_) {
      routeState.value = null;
    }
  }

  Future<Map<String, dynamic>> loadRouteInfo() async {
    try {
      final state = tripState.value;
      final response = await api.getDriverRouteInfo(
        vehicleId: state.vehicleId,
        routeId: _activeRouteId,
        assignmentId: state.assignmentId,
        driverId: state.driverId,
      );
      debugPrint('MAP_ROUTE_LOAD_RESPONSE: $response');
      final route = response['route'];
      if (route is Map<String, dynamic>) {
        debugPrint('ROUTE_INFO_DATA: $route');
        routeState.value = route;
        _activeRouteId = route['route_id']?.toString() ?? _activeRouteId;
        tripState.value = tripState.value.copyWith(
          routeId: _activeRouteId,
          clearError: true,
        );
        return route;
      }
    } catch (e) {
      debugPrint('MAP_ROUTE_LOAD_RESPONSE_ERROR: $e');
      if (tripState.value.assignmentId != null) {
        tripState.value = tripState.value.copyWith(
          lastError: 'Route path not available',
        );
        routeState.value = null;
        rethrow;
      }
    }
    if (routeState.value == null) {
      throw Exception('no routes active');
    }
    return routeState.value!;
  }

  Future<Map<String, dynamic>> advanceRouteStop() async {
    try {
      final currentRouteId =
          routeState.value?['route_id']?.toString() ?? _activeRouteId;
      final normalizedRouteId = currentRouteId.trim().toLowerCase();
      final hasMockRoute = mockRoutes.keys.any(
        (k) => k.toLowerCase() == normalizedRouteId,
      );
      if (hasMockRoute) {
        throw const FormatException('Use local route fallback');
      }
      final response = await api.advanceDriverRoute(
        vehicleId: tripState.value.vehicleId,
        routeId: currentRouteId,
        assignmentId: tripState.value.assignmentId,
      );
      final route = response['route'];
      if (route is Map<String, dynamic>) {
        routeState.value = route;
        _activeRouteId = route['route_id']?.toString() ?? currentRouteId;
        tripState.value = tripState.value.copyWith(
          routeId: _activeRouteId,
          clearError: true,
        );
        return route;
      }
    } catch (e) {
      debugPrint('advanceRouteStop error: $e');
      rethrow;
    }
    if (routeState.value == null) {
      throw Exception('no routes active');
    }
    return routeState.value!;
  }

  Future<void> flushQueuedLocations() async {
    if (_queuedObservations.isEmpty) return;

    final batch = List<Map<String, dynamic>>.from(_queuedObservations);
    for (final observation in batch) {
      await api.sendVehicleLocation(observation: observation);
      _queuedObservations.remove(observation);
    }
    tripState.value = tripState.value.copyWith(
      queuedCount: _queuedObservations.length,
      clearError: true,
    );
  }

  Future<void> logout() async {
    await endTrip();
    api.clearAuthToken();
    _driverId = defaultDriverId;
    _vehicleId = defaultVehicleId;
    tripState.value = tripState.value.copyWith(
      vehicleId: _vehicleId,
      clearError: true,
      queuedCount: _queuedObservations.length,
    );
  }

  Future<void> _sendCurrentLocation() async {
    if (_sendingTick) return;
    final currentState = tripState.value;
    if (!currentState.active || currentState.assignmentId == null) {
      debugPrint(
          'DRIVER_LOCATION_UPDATE: skipped inactive assignment active=${currentState.active} assignment_id=${currentState.assignmentId}');
      return;
    }
    _sendingTick = true;
    tripState.value = tripState.value.copyWith(sending: true, clearError: true);

    try {
      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      debugPrint('DRIVER_LOCATION_UPDATE_RAW: lat=${position.latitude} lng=${position.longitude} timestamp=${position.timestamp}');
      if (position.latitude >= -90.0 && position.latitude <= 90.0 && position.longitude >= -180.0 && position.longitude <= 180.0) {
        debugPrint('DRIVER_LOCATION_UPDATE_VALIDATED: lat=${position.latitude} lng=${position.longitude} timestamp=${position.timestamp}');
      }
      tripState.value = tripState.value.copyWith(
        lastPosition: position,
        queuedCount: _queuedObservations.length,
      );
      final observation = _observationFromPosition(position);

      if (_queuedObservations.isNotEmpty) {
        await flushQueuedLocations();
      }

      await api.sendVehicleLocation(observation: observation);
      tripState.value = tripState.value.copyWith(
        sending: false,
        lastPosition: position,
        lastSentAt: DateTime.now().toUtc(),
        clearError: true,
        queuedCount: _queuedObservations.length,
      );
    } catch (error) {
      final position = tripState.value.lastPosition;
      final apiError = error is ApiException ? error : null;
      if (apiError?.statusCode == 404) {
        _locationTimer?.cancel();
        _locationTimer = null;
      } else if (position != null) {
        _queuedObservations.add(_observationFromPosition(position));
      }

      tripState.value = tripState.value.copyWith(
        active: apiError?.statusCode == 404 ? false : null,
        sending: false,
        lastError: _friendlyError(error),
        queuedCount: _queuedObservations.length,
      );
    } finally {
      _sendingTick = false;
    }
  }

  Map<String, dynamic> _observationFromPosition(Position position) {
    final state = tripState.value;
    return {
      'assignment_id': state.assignmentId,
      'trip_id': state.tripId,
      'driver_id': state.driverId ?? _driverId,
      'vehicle_id': state.vehicleId,
      'route_id': state.routeId,
      'lat': position.latitude,
      'lng': position.longitude,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
      'speed': position.speed.isFinite && position.speed >= 0
          ? position.speed
          : null,
      'heading': position.heading.isFinite && position.heading >= 0
          ? position.heading
          : null,
      'source': 'driver_app',
    };
  }

  Future<void> _ensureLocationReady() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    debugPrint('DRIVER_LOCATION_SERVICE_ENABLED: $serviceEnabled');
    if (!serviceEnabled) {
      throw const ApiException(
          'Turn on location services on your phone first.');
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    debugPrint('DRIVER_LOCATION_PERMISSION_STATUS: $permission');

    if (permission == LocationPermission.denied) {
      throw const ApiException('Location permission is required to share live trip location.');
    }

    if (permission == LocationPermission.deniedForever) {
      throw const ApiException(
        'Location permission is permanently denied. Enable it from app settings.',
      );
    }
  }

  String _friendlyError(Object error) {
    if (error is ApiException && error.statusCode == 404) {
      return 'Backend route /driver/location was not found at ${ApiConfig.baseUrl}. Check that the driver app is connected to the same backend that supports vehicle tracking.';
    }

    final message = error.toString().replaceFirst('Exception: ', '');
    if (message.contains('SocketException') ||
        message.contains('Connection refused') ||
        message.contains('timed out')) {
      return 'Cannot reach backend at ${ApiConfig.baseUrl}. Check FastAPI server and adb reverse.';
    }
    return message;
  }

  String _severityForCategory(String category) {
    final normalized = category.toLowerCase();
    if (normalized.contains('emergency') ||
        normalized.contains('accident') ||
        normalized.contains('breakdown')) {
      return 'critical';
    }
    if (normalized.contains('traffic') || normalized.contains('deviation')) {
      return 'warning';
    }
    return 'info';
  }

  Future<void> initSettings() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final settings = Map<String, dynamic>.from(appSettings.value);
      settings['language'] = prefs.getString('language') ?? 'en';
      settings['theme'] = prefs.getString('theme') ?? 'system';
      settings['notificationsEnabled'] = prefs.getBool('notificationsEnabled') ?? true;
      settings['locationUpdateInterval'] = prefs.getInt('locationUpdateInterval') ?? 10;
      settings['autoSendLocation'] = prefs.getBool('autoSendLocation') ?? true;
      settings['keepScreenAwake'] = prefs.getBool('keepScreenAwake') ?? true;
      settings['showStopAdvancement'] = prefs.getBool('showStopAdvancement') ?? true;
      appSettings.value = settings;
      debugPrint('IZEE Settings: Local settings loaded successfully');
    } catch (e) {
      debugPrint('IZEE Settings: Failed to load local settings: $e');
    }
  }

  Future<void> updateSetting(String key, dynamic value) async {
    final settings = Map<String, dynamic>.from(appSettings.value);
    settings[key] = value;
    appSettings.value = settings;

    try {
      final prefs = await SharedPreferences.getInstance();
      if (value is String) {
        await prefs.setString(key, value);
      } else if (value is bool) {
        await prefs.setBool(key, value);
      } else if (value is int) {
        await prefs.setInt(key, value);
      }
      debugPrint('IZEE Settings: Setting "$key" saved as $value');
    } catch (e) {
      debugPrint('IZEE Settings: Failed to save setting "$key": $e');
    }

    if (key == 'locationUpdateInterval' || key == 'autoSendLocation') {
      if (tripState.value.active) {
        _locationTimer?.cancel();
        if (appSettings.value['autoSendLocation'] == true) {
          final interval = appSettings.value['locationUpdateInterval'] as int? ?? 10;
          _locationTimer = Timer.periodic(Duration(seconds: interval), (_) => _sendCurrentLocation());
          tripState.value = tripState.value.copyWith(sending: true);
        } else {
          tripState.value = tripState.value.copyWith(sending: false);
        }
      }
    }
  }

  void dispose() {
    _locationTimer?.cancel();
    _messageRefreshTimer?.cancel();
    _messageSocket?.close();
    _messageSocketPingTimer?.cancel();
    tripState.dispose();
    routeState.dispose();
    unreadCount.dispose();
    api.dispose();
  }
}
