import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiConfig {
  const ApiConfig._();

  static const baseUrl = String.fromEnvironment(
    'IZEE_API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const routingAlgorithmUrl = String.fromEnvironment(
    'IZEE_ROUTING_ALGORITHM_URL',
    defaultValue: '',
  );

  static const liveVehicles = '/vehicles/live';
  static const geocodeSearch = '/geocode/search';
  static const placesSearch = '/places/search';
  static const routeSearch = '/trip-plan';
  static const routeDetails = '/routes';
  static const wallet = '/wallet';
  static const notifications = '/notifications';
  static const profile = '/profile';
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

  Future<Map<String, dynamic>> getLiveVehicles() {
    return get(ApiConfig.liveVehicles);
  }

  Future<Map<String, dynamic>> getRouteVehicles(String routeId) {
    return get('/passenger/routes/$routeId/vehicles');
  }

  Future<Map<String, dynamic>> searchPlaces(String query) {
    return get(
      ApiConfig.placesSearch,
      query: {'query': query, 'limit': '10'},
    );
  }

  Future<Map<String, dynamic>> searchRoutes({
    required Map<String, double> origin,
    required Map<String, double> destination,
    String departureTime = 'now',
    int maxTransfers = 4,
    bool useWalking = true,
  }) async {
    final data = await postRoutingAlgorithm(
      body: {
        'origin': origin,
        'destination': destination,
        'departure_time': departureTime,
        'max_transfers': maxTransfers,
        'use_walking': useWalking,
      },
    );
    _logRouteResponse(data);
    return data;
  }

  Future<Map<String, dynamic>> getRouteDetails(String routeId) {
    return get('${ApiConfig.routeDetails}/$routeId');
  }

  Future<Map<String, dynamic>> getWallet() {
    return get(ApiConfig.wallet);
  }

  Future<Map<String, dynamic>> getNotifications() {
    return get(ApiConfig.notifications);
  }

  Future<Map<String, dynamic>> getProfile() {
    return get(ApiConfig.profile);
  }

  Future<Map<String, dynamic>> getFavorites() {
    return get('/passenger/favorites');
  }

  Future<Map<String, dynamic>> addFavorite(Map<String, dynamic> body) {
    return post('/passenger/favorites', body: body);
  }

  Future<Map<String, dynamic>> deleteFavorite(String routeId) {
    return delete('/passenger/favorites/$routeId');
  }

  Future<Map<String, dynamic>> get(
    String endpoint, {
    Map<String, String>? query,
  }) async {
    final uri = _uri(endpoint, query);
    _logUrl('GET', uri);
    try {
      final response = await _client
          .get(
            uri,
            headers: _headers,
          )
          .timeout(const Duration(seconds: 30));
      return _decode(response);
    } catch (e) {
      print('IZEE API GET ERROR for $uri: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> post(
    String endpoint, {
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(endpoint);
    _logUrl('POST', uri);
    try {
      final response = await _client
          .post(
            uri,
            headers: _headers,
            body: jsonEncode(body ?? {}),
          )
          .timeout(const Duration(seconds: 30));
      return _decode(response);
    } catch (e) {
      print('IZEE API POST ERROR for $uri: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> delete(
    String endpoint, {
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(endpoint);
    _logUrl('DELETE', uri);
    try {
      final response = await _client
          .delete(
            uri,
            headers: _headers,
            body: jsonEncode(body ?? {}),
          )
          .timeout(const Duration(seconds: 30));
      return _decode(response);
    } catch (e) {
      print('IZEE API DELETE ERROR for $uri: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> postRoutingAlgorithm({
    required Map<String, dynamic> body,
  }) async {
    final uri = ApiConfig.routingAlgorithmUrl.isEmpty
        ? _uri(
            ApiConfig.routeSearch,
            const {'street_geometry': 'true'},
          )
        : Uri.parse(ApiConfig.routingAlgorithmUrl);
    _logUrl('POST', uri);
    final response = await _client
        .post(
          uri,
          headers: _headers,
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 600));
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
      data['message']?.toString() ?? 'Request failed',
      statusCode: response.statusCode,
    );
  }

  void dispose() {
    _client.close();
  }

  void _logUrl(String method, Uri uri) {
    // ignore: avoid_print
    print('IZEE API $method $uri');
  }

  void _logRouteResponse(Map<String, dynamic> data) {
    final routes = data['routes'];
    final routeList = routes is List ? routes : const [];
    // ignore: avoid_print
    print('IZEE /trip-plan returned ${routeList.length} route(s)');

    for (var i = 0; i < routeList.length; i++) {
      final route = routeList[i];
      if (route is! Map) continue;

      final legs = route['legs'];
      final legList = legs is List ? legs : const [];
      final modes = <String>[];
      final labels = <String>[];

      for (final leg in legList) {
        if (leg is! Map) continue;
        final mode = leg['mode']?.toString();
        if (mode != null && mode.isNotEmpty) modes.add(mode);
        final label = (leg['route_label'] ?? leg['route_id'])?.toString();
        if (label != null && label.isNotEmpty && label != 'null') {
          labels.add(label);
        }
      }

      final type = route['ranking_type'] ??
          route['alternative_type'] ??
          route['label'] ??
          route['badges'];
      // ignore: avoid_print
      print(
        'Route $i: type=$type, transfers=${route['transfer_count']}, '
        'time=${route['total_travel_time']}, '
        'walking=${route['total_walking_time']}, '
        'cost=${route['generalized_cost']}, '
        'modes=$modes, route_labels=$labels',
      );
    }
  }
}
