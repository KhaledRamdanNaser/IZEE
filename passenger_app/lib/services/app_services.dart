import 'api_service.dart';

class AppServices {
  AppServices({ApiService? api}) : api = api ?? ApiService();

  final ApiService api;
  final Map<String, List<Map<String, dynamic>>> _placeCache = {};

  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final token = 'local-passenger-token-${email.trim()}';
    api.setAuthToken(token);
    return {
      'status': 'local_login',
      'email': email.trim(),
      'token': token,
    };
  }

  Future<Map<String, dynamic>> signUp({
    required String name,
    required String phone,
    required String email,
    required String password,
  }) async {
    final token = 'local-passenger-token-${email.trim()}';
    api.setAuthToken(token);
    return {
      'status': 'local_signup',
      'name': name.trim(),
      'phone': phone.trim(),
      'email': email.trim(),
      'token': token,
    };
  }

  Future<Map<String, dynamic>> loadHome() {
    return api.getLiveVehicles();
  }

  Future<Map<String, dynamic>> calculateRoute({
    required String origin,
    required String destination,
  }) async {
    return api.searchRoutes(
      origin: await _resolveLocation(origin),
      destination: await _resolveLocation(destination),
    );
  }

  Future<Map<String, dynamic>> calculateRouteFromCoordinates({
    required Map<String, double> origin,
    required Map<String, double> destination,
    String departureTime = 'now',
  }) {
    return api.searchRoutes(origin: origin, destination: destination, departureTime: departureTime);
  }

  Future<List<Map<String, dynamic>>> searchPlaces(String query) async {
    final normalized = query.trim().toLowerCase();
    if (normalized.length < 2) return const [];

    final cached = _placeCache[normalized];
    if (cached != null && cached.isNotEmpty) {
      print('SEARCH_QUERY $query');
      print('SEARCH_ENDPOINT ${ApiConfig.baseUrl}${ApiConfig.placesSearch}');
      print('SEARCH_RESPONSE cached');
      print('SUGGESTIONS_COUNT ${cached.length}');
      return cached;
    }

    print('SEARCH_QUERY $query');
    print('SEARCH_ENDPOINT ${ApiConfig.baseUrl}${ApiConfig.placesSearch}');
    final data = await api.searchPlaces(query.trim());
    print('SEARCH_RESPONSE $data');
    final results = data['results'];
    if (results is! List) {
      print('SUGGESTIONS_COUNT 0');
      return const [];
    }

    final places = results.whereType<Map<String, dynamic>>().map((place) {
      return {
        'name': place['name']?.toString() ?? query.trim(),
        'lat': _toDouble(place['lat']),
        'lon': _toDouble(place['lon']),
        'result_type': place['result_type'] ?? place['type'],
        'type': place['type'] ?? place['result_type'],
        'mode': place['mode'],
        'source': place['source'],
        'subtitle': place['subtitle'],
      };
    }).toList();

    print('SUGGESTIONS_COUNT ${places.length}');
    if (places.isNotEmpty) {
      _placeCache[normalized] = places;
    } else {
      _placeCache.remove(normalized);
    }
    return places;
  }

  Future<Map<String, dynamic>> loadRouteDetails([String? routeId]) {
    if (routeId == null || routeId.isEmpty) {
      throw const ApiException('Select a backend route first.');
    }
    return api.getRouteDetails(routeId);
  }

  Future<Map<String, dynamic>> loadRouteVehicles(String routeId) {
    if (routeId.isEmpty) {
      throw const ApiException('Select a backend route first.');
    }
    return api.getRouteVehicles(routeId);
  }

  Future<Map<String, dynamic>> loadWallet() {
    return api.getWallet();
  }

  Future<Map<String, dynamic>> loadNotifications() {
    return api.getNotifications();
  }

  Future<Map<String, dynamic>> loadProfile() {
    return api.getProfile();
  }

  Future<List<Map<String, dynamic>>> loadFavorites() async {
    try {
      final res = await api.getFavorites();
      final data = res['data'];
      if (data is List) {
        return data.whereType<Map<String, dynamic>>().toList();
      }
      return const [];
    } catch (e) {
      print('Error loading favorites: $e');
      return const [];
    }
  }

  Future<Map<String, dynamic>> addFavorite({
    required String routeId,
    required String routeName,
    required double originLat,
    required double originLon,
    required double destinationLat,
    required double destinationLon,
    required String originName,
    required String destinationName,
  }) {
    return api.addFavorite({
      'route_id': routeId,
      'route_name': routeName,
      'origin_lat': originLat,
      'origin_lon': originLon,
      'destination_lat': destinationLat,
      'destination_lon': destinationLon,
      'origin_name': originName,
      'destination_name': destinationName,
    });
  }

  Future<Map<String, dynamic>> deleteFavorite(String routeId) {
    return api.deleteFavorite(routeId);
  }

  Future<Map<String, dynamic>> topUpWallet(double amount) {
    return api.post('${ApiConfig.wallet}/top-up', body: {'amount': amount});
  }

  Future<Map<String, dynamic>> createTicketScan() {
    return api.post('${ApiConfig.wallet}/ticket/scan');
  }

  Future<Map<String, dynamic>> saveTicket() {
    return api.post('${ApiConfig.wallet}/ticket/save');
  }

  Future<Map<String, dynamic>> addPaymentMethod({
    required String cardHolder,
    required String cardNumber,
    required String cardType,
    required String expiry,
  }) {
    return api.post('${ApiConfig.wallet}/payment-methods', body: {
      'card_holder': cardHolder,
      'card_number': cardNumber,
      'card_type': cardType,
      'expiry': expiry,
    });
  }

  Future<Map<String, dynamic>> activatePaymentMethod(int pmId) {
    return api.post('${ApiConfig.wallet}/payment-methods/$pmId/activate');
  }

  Future<Map<String, dynamic>> deactivateAllPaymentMethods() {
    return api.post('${ApiConfig.wallet}/payment-methods/deactivate-all');
  }

  Future<Map<String, dynamic>> deletePaymentMethod(int pmId) {
    return api.delete('${ApiConfig.wallet}/payment-methods/$pmId');
  }

  Future<Map<String, dynamic>> reportIncident({
    required String category,
    required String severity,
    required String details,
    String? vehicleId,
    String? routeId,
    String? locationLabel,
    double? lat,
    double? lon,
  }) {
    return api.post('/incidents', body: {
      'category': category,
      'severity': severity,
      'details': details,
      'vehicle_id': vehicleId,
      'route_id': routeId,
      'location_label': locationLabel,
      'lat': lat,
      'lon': lon,
      'source': 'passenger_app',
    });
  }

  Future<Map<String, dynamic>> markNotificationsRead() {
    return api.post('${ApiConfig.notifications}/mark-read');
  }

  Future<Map<String, dynamic>> markSingleNotificationRead(String notificationId) {
    return api.post('${ApiConfig.notifications}/$notificationId/mark-read');
  }

  Future<Map<String, dynamic>> startTrip([String? routeId]) async {
    if (routeId == null || routeId.isEmpty) {
      throw const ApiException('Select a backend route first.');
    }
    try {
      return await api.post('${ApiConfig.routeDetails}/$routeId/start');
    } on ApiException catch (error) {
      if (error.statusCode == 404) {
        return {'status': 'navigation_started', 'route_id': routeId};
      }
      rethrow;
    }
  }

  Future<Map<String, dynamic>> cancelTrip([String? routeId]) {
    if (routeId == null || routeId.isEmpty) {
      throw const ApiException('Select a backend route first.');
    }
    return api.post('${ApiConfig.routeDetails}/$routeId/cancel');
  }

  Future<Map<String, dynamic>> shareTrip([String? routeId]) {
    if (routeId == null || routeId.isEmpty) {
      throw const ApiException('Select a backend route first.');
    }
    return api.post('${ApiConfig.routeDetails}/$routeId/share');
  }

  Future<Map<String, dynamic>> callDriver([String? routeId]) {
    if (routeId == null || routeId.isEmpty) {
      throw const ApiException('Select a backend route first.');
    }
    return api.post('${ApiConfig.routeDetails}/$routeId/driver/call');
  }

  Future<Map<String, dynamic>> logout() async {
    api.clearAuthToken();
    return {'status': 'local_logout'};
  }

  void dispose() {
    api.dispose();
  }

  Future<Map<String, double>> _resolveLocation(String value) async {
    final places = await searchPlaces(value);
    if (places.isEmpty) {
      throw ApiException('No geocoding results for "$value"');
    }
    return {
      'lat': _toDouble(places.first['lat']),
      'lon': _toDouble(places.first['lon']),
    };
  }

  double _toDouble(Object? value) {
    if (value is num) return value.toDouble();
    return double.parse(value.toString());
  }
}
