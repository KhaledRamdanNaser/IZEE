import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiConfig {
  const ApiConfig._();

  static const baseUrl = String.fromEnvironment(
    'IZEE_API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const vehicleLocation = '/driver/location';
  static const incidents = '/incidents';
  static const messages = '/messages';
  static const driverAssignedDuties = '/driver/assigned-duties';
  static const driverRouteInfo = '/driver/route-info';
}

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() {
    if (statusCode == null) return message;
    return '$message (status $statusCode)';
  }
}

class ApiService {
  ApiService({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  String? _authToken;

  void setAuthToken(String token) {
    _authToken = token;
  }

  void clearAuthToken() {
    _authToken = null;
  }

  Future<Map<String, dynamic>> sendVehicleLocation({
    required Map<String, dynamic> observation,
  }) async {
    final url = '${ApiConfig.baseUrl}${ApiConfig.vehicleLocation}';
    final headers = _headers;
    print('DRIVER_LOCATION_POST_URL: $url');
    print('DRIVER_LOCATION_POST_HEADERS: $headers');
    print('DRIVER_LOCATION_POST_PAYLOAD: $observation');
    try {
      final uri = _uri(ApiConfig.vehicleLocation);
      final response = await _client.post(
        uri,
        headers: headers,
        body: jsonEncode(observation),
      ).timeout(const Duration(seconds: 30));
      print('DRIVER_LOCATION_POST_STATUS: ${response.statusCode}');
      print('DRIVER_LOCATION_POST_RESPONSE: ${response.body}');
      return _decode(response);
    } catch (e) {
      print('DRIVER_LOCATION_POST_ERROR: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> createIncident({
    required Map<String, dynamic> incident,
  }) {
    return post(ApiConfig.incidents, body: incident);
  }

  Future<Map<String, dynamic>> getMessages({
    String? recipientId,
  }) {
    return get(
      ApiConfig.messages,
      query: {
        if (recipientId != null && recipientId.isNotEmpty)
          'recipient_id': recipientId,
        'limit': '100',
      },
    );
  }

  Future<Map<String, dynamic>> markMessageRead(String messageId) {
    return post('${ApiConfig.messages}/$messageId/read');
  }

  Future<Map<String, dynamic>> getDriverRouteInfo({
    required String vehicleId,
    String? routeId,
    String? assignmentId,
    String? driverId,
  }) {
    return get(
      ApiConfig.driverRouteInfo,
      query: {
        'vehicle_id': vehicleId,
        if (routeId != null && routeId.isNotEmpty) 'route_id': routeId,
        if (assignmentId != null && assignmentId.isNotEmpty)
          'assignment_id': assignmentId,
        if (driverId != null && driverId.isNotEmpty) 'driver_id': driverId,
      },
    );
  }

  Future<Map<String, dynamic>> getDriverAssignedDuties({
    required String vehicleId,
  }) {
    return get(
      ApiConfig.driverAssignedDuties,
      query: {
        'vehicle_id': vehicleId,
        'limit': '5',
      },
    );
  }

  Future<Map<String, dynamic>> getDriverTripHistory({
    required String driverId,
  }) {
    return get('/driver/$driverId/trip-history');
  }

  Future<Map<String, dynamic>> clearDriverTripHistory({
    required String driverId,
  }) {
    return post('/driver/$driverId/trip-history/clear');
  }

  Future<Map<String, dynamic>> getDriverAssignments({
    required String driverId,
  }) {
    return get('/driver/$driverId/duties');
  }

  Future<Map<String, dynamic>> startAssignment({
    required String assignmentId,
    String? driverId,
  }) {
    return post(
      '/driver/assignments/$assignmentId/start',
      query: {
        if (driverId != null && driverId.isNotEmpty) 'driver_id': driverId,
      },
    );
  }

  Future<Map<String, dynamic>> completeAssignment({
    required String assignmentId,
  }) {
    return post('/driver/assignments/$assignmentId/complete');
  }

  Future<Map<String, dynamic>> advanceDriverRoute({
    required String vehicleId,
    String? routeId,
    String? assignmentId,
  }) {
    return post(
      '${ApiConfig.driverRouteInfo}/advance',
      query: {
        'vehicle_id': vehicleId,
        if (routeId != null && routeId.isNotEmpty) 'route_id': routeId,
        if (assignmentId != null && assignmentId.isNotEmpty)
          'assignment_id': assignmentId,
      },
      body: {
        'vehicle_id': vehicleId,
        if (routeId != null && routeId.isNotEmpty) 'route_id': routeId,
        if (assignmentId != null && assignmentId.isNotEmpty)
          'assignment_id': assignmentId,
      },
    );
  }

  Future<Map<String, dynamic>> get(
    String endpoint, {
    Map<String, String>? query,
  }) async {
    final uri = _uri(endpoint, query);
    _logUrl('GET', uri);
    final response = await _client
        .get(uri, headers: _headers)
        .timeout(const Duration(seconds: 30));
    return _decode(response);
  }

  Future<Map<String, dynamic>> post(
    String endpoint, {
    Map<String, String>? query,
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(endpoint, query);
    _logUrl('POST', uri);
    final response = await _client
        .post(
          uri,
          headers: _headers,
          body: jsonEncode(body ?? {}),
        )
        .timeout(const Duration(seconds: 30));
    return _decode(response);
  }

  Map<String, String> get _headers {
    return {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      if (_authToken != null) 'Authorization': 'Bearer $_authToken',
    };
  }

  Uri _uri(String endpoint, [Map<String, String>? query]) {
    final base = Uri.parse(ApiConfig.baseUrl);
    final normalizedEndpoint =
        endpoint.startsWith('/') ? endpoint : '/$endpoint';
    return base.replace(
      path: '${base.path}$normalizedEndpoint',
      queryParameters: query,
    );
  }

  Map<String, dynamic> _decode(http.Response response) {
    final decoded =
        response.body.isEmpty ? <String, dynamic>{} : jsonDecode(response.body);
    final data = decoded is Map<String, dynamic>
        ? decoded
        : <String, dynamic>{'data': decoded};

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return data;
    }

    throw ApiException(
      data['message']?.toString() ??
          data['detail']?.toString() ??
          'Request failed',
      statusCode: response.statusCode,
    );
  }

  void dispose() {
    _client.close();
  }

  void _logUrl(String method, Uri uri) {
    // ignore: avoid_print
    print('IZEE Driver API $method $uri');
  }
}
