import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'services/app_services.dart';
import 'services/api_service.dart';

void main() {
  runApp(const IzeeApp());
}

const green = Color(0xFF10B981);
const darkGreen = Color(0xFF009F72);
const paleGreen = Color(0xFFEAFBF5);
const ink = Color(0xFF0F172A);
const muted = Color(0xFF64748B);
const softLine = Color(0xFFE5E7EB);
const rose = Color(0xFFE11D48);

IconData iconForMode(String mode) {
  final normalized = mode.toLowerCase();
  if (normalized.contains('walk')) return Icons.directions_walk;
  if (normalized.contains('metro') || normalized == 'm') return Icons.subway;
  if (normalized.contains('microbus') || normalized.contains('van')) {
    return Icons.airport_shuttle;
  }
  if (normalized.contains('minibus')) return Icons.directions_bus_filled;
  if (normalized.contains('brt')) return Icons.directions_bus;
  if (normalized.contains('lrt') || normalized.contains('tram')) {
    return Icons.tram;
  }
  if (normalized.contains('mono')) return Icons.train;
  return Icons.directions_bus;
}

Color colorForMode(String mode) {
  final normalized = mode.toLowerCase();
  if (normalized.contains('walk')) return const Color(0xFF64748B);
  if (normalized.contains('metro') || normalized == 'm') {
    return const Color(0xFF2563EB);
  }
  if (normalized.contains('microbus') || normalized.contains('van')) {
    return const Color(0xFFF59E0B);
  }
  if (normalized.contains('minibus')) return const Color(0xFF8B5CF6);
  if (normalized.contains('brt')) return const Color(0xFFDC2626);
  if (normalized.contains('lrt') || normalized.contains('tram')) {
    return const Color(0xFF0891B2);
  }
  if (normalized.contains('mono')) return const Color(0xFF7C3AED);
  return green;
}

String labelForMode(String mode) {
  final normalized = mode.toLowerCase();
  if (normalized.contains('walk')) return 'Walk';
  if (normalized.contains('metro') || normalized == 'm') return 'Metro';
  if (normalized.contains('microbus') || normalized.contains('van')) {
    return 'Microbus';
  }
  if (normalized.contains('minibus')) return 'Minibus';
  if (normalized.contains('brt')) return 'BRT';
  if (normalized.contains('lrt') || normalized.contains('tram')) return 'LRT';
  if (normalized.contains('mono')) return 'Monorail';
  if (normalized.contains('bus')) return 'Bus';
  return mode.isEmpty ? 'Route' : mode;
}

typedef BackendConnector = Future<bool> Function(
  String action,
  Future<Map<String, dynamic>> Function() request, {
  bool quiet,
});

enum AppScreen {
  splash,
  auth,
  home,
  planTrip,
  routeDetails,
  wallet,
  notifications,
  profile,
  favorites,
  tripHistory,
}

class PlanTripSession {
  String originText = '';
  String destinationText = '';
  Map<String, double>? selectedOrigin;
  Map<String, double>? selectedDestination;
  Map<String, dynamic>? routeResponse;
  String? errorMessage;
  String selectedDepartureTime = 'now';
  String? lastSearchRequest;
  bool loadingRoutes = false;
  final Map<String, List<Map<String, dynamic>>> geocodeCache = {};
  final List<RecentTripSearch> recentSearches = [];
}

class RecentTripSearch {
  const RecentTripSearch({
    required this.originText,
    required this.destinationText,
    required this.origin,
    required this.destination,
  });

  final String originText;
  final String destinationText;
  final Map<String, double> origin;
  final Map<String, double> destination;

  String get label => '$originText -> $destinationText';
}

class IzeeApp extends StatelessWidget {
  const IzeeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'IZEE',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: green),
        fontFamily: 'Roboto',
        scaffoldBackgroundColor: Colors.white,
      ),
      home: const AppShell(),
    );
  }
}

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  AppScreen screen = AppScreen.splash;
  bool showTicket = false;
  bool menuOpen = false;
  Map<String, dynamic>? selectedRoute;
  final PlanTripSession planTripSession = PlanTripSession();
  late final AppServices services = AppServices();

  @override
  void dispose() {
    services.dispose();
    super.dispose();
  }

  void go(AppScreen next) {
    setState(() {
      menuOpen = false;
      screen = next;
      if (next != AppScreen.wallet) showTicket = false;
    });
  }

  void setMenuOpen(bool open) {
    setState(() => menuOpen = open);
  }

  Future<bool> connect(
    String action,
    Future<Map<String, dynamic>> Function() request, {
    bool quiet = false,
  }) async {
    try {
      await request();
      if (!quiet && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$action connected')),
        );
      }
      return true;
    } catch (error) {
      if (!quiet && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '$action is ready, but the backend did not respond yet.',
            ),
          ),
        );
      }
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      backgroundColor: const Color(0xFFF8FAFC),
      body: LayoutBuilder(
        builder: (context, constraints) {
          return Align(
            alignment: Alignment.topCenter,
            child: ConstrainedBox(
              constraints: BoxConstraints(
                maxWidth: 420,
                minHeight: constraints.maxHeight,
                maxHeight: constraints.maxHeight,
              ),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  color: Colors.white,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: .08),
                      blurRadius: 24,
                      offset: const Offset(0, 12),
                    ),
                  ],
                ),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    _body(),
                    AnimatedSwitcher(
                      duration: const Duration(milliseconds: 220),
                      child: menuOpen
                          ? MenuOverlay(
                              key: const ValueKey('menu-overlay'),
                              onClose: () => setMenuOpen(false),
                              onGo: go,
                            )
                          : const SizedBox.shrink(),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _body() {
    switch (screen) {
      case AppScreen.splash:
        return SplashScreen(onStart: () => go(AppScreen.auth));
      case AppScreen.auth:
        return AuthScreen(
          services: services,
          connect: connect,
          onDone: () => go(AppScreen.home),
        );
      case AppScreen.home:
        return HomeScreen(
          services: services,
          connect: connect,
          onOpenMenu: () => setMenuOpen(true),
          onGo: go,
          onRouteSelected: (route) => selectedRoute = route,
          selectedRoute: selectedRoute,
        );
      case AppScreen.planTrip:
        return PlanTripScreen(
          services: services,
          connect: connect,
          onGo: go,
          session: planTripSession,
          onRouteSelected: (route) {
            setState(() => selectedRoute = route);
            go(AppScreen.routeDetails);
          },
        );
      case AppScreen.routeDetails:
        return RouteDetailsScreen(
          services: services,
          connect: connect,
          onGo: go,
          route: selectedRoute,
        );
      case AppScreen.wallet:
        return WalletScreen(
          services: services,
          connect: connect,
          onGo: go,
          showTicket: showTicket,
          onToggleTicket: () async =>
              setState(() => showTicket = !showTicket),
        );
      case AppScreen.notifications:
        return NotificationsScreen(
          services: services,
          connect: connect,
          onGo: go,
        );
      case AppScreen.profile:
        return ProfileScreen(
          services: services,
          connect: connect,
          onGo: go,
        );
      case AppScreen.favorites:
        return SimpleListScreen(
          title: 'Favorites',
          emptyText: 'No favorite places yet',
          onBack: () => go(AppScreen.home),
        );
      case AppScreen.tripHistory:
        return SimpleListScreen(
          title: 'Trip History',
          emptyText: 'No completed trips yet',
          onBack: () => go(AppScreen.home),
        );
    }
  }
}

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key, required this.onStart});

  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: darkGreen,
      padding: const EdgeInsets.fromLTRB(20, 40, 20, 28),
      child: SafeArea(
        child: Column(
          children: [
            const Spacer(),
            Container(
              width: 154,
              height: 154,
              decoration: const BoxDecoration(
                color: Colors.white,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.directions_bus, color: green, size: 76),
            ),
            const SizedBox(height: 30),
            const Text(
              'IZEE',
              style: TextStyle(
                color: Colors.white,
                fontSize: 34,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Smart Public Transport',
              style: TextStyle(color: Colors.white, fontSize: 14),
            ),
            const Spacer(),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: FilledButton(
                onPressed: onStart,
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: green,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(9),
                  ),
                ),
                child: const Text(
                  'Get Started',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AuthScreen extends StatefulWidget {
  const AuthScreen({
    super.key,
    required this.services,
    required this.connect,
    required this.onDone,
  });

  final AppServices services;
  final BackendConnector connect;
  final VoidCallback onDone;

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  bool signUp = false;
  final nameController = TextEditingController(text: 'Ahmed Hassan');
  final phoneController = TextEditingController(text: '+20 123 456 7890');
  final emailController = TextEditingController(text: 'ahmed.hassan@email.com');
  final passwordController = TextEditingController(text: 'password123');

  @override
  void dispose() {
    nameController.dispose();
    phoneController.dispose();
    emailController.dispose();
    passwordController.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (signUp) {
      await widget.connect(
        'Sign up',
        () => widget.services.signUp(
          name: nameController.text,
          phone: phoneController.text,
          email: emailController.text,
          password: passwordController.text,
        ),
      );
    } else {
      await widget.connect(
        'Login',
        () => widget.services.login(
          email: emailController.text,
          password: passwordController.text,
        ),
      );
    }
    widget.onDone();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(18, 36, 18, 26),
          decoration: const BoxDecoration(
            color: green,
            borderRadius: BorderRadius.vertical(bottom: Radius.circular(12)),
            boxShadow: [
              BoxShadow(
                color: Color(0x24000000),
                blurRadius: 18,
                offset: Offset(0, 8),
              ),
            ],
          ),
          child: const SafeArea(
            bottom: false,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.directions_bus, color: Colors.white),
                    SizedBox(width: 9),
                    Text(
                      'IZEE',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 24,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ),
                SizedBox(height: 8),
                Text(
                  'Your smart travel companion',
                  style: TextStyle(color: Colors.white, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 36, 20, 24),
            children: [
              Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: const Color(0xFFE9E9EE),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: _AuthTab(
                        label: 'Login',
                        active: !signUp,
                        onTap: () => setState(() => signUp = false),
                      ),
                    ),
                    Expanded(
                      child: _AuthTab(
                        label: 'Sign Up',
                        active: signUp,
                        onTap: () => setState(() => signUp = true),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              if (signUp) ...[
                FormFieldBox(
                    controller: nameController,
                    label: 'Full Name',
                    hint: 'Enter your name',
                    icon: Icons.person_outline),
                FormFieldBox(
                    controller: phoneController,
                    label: 'Phone Number',
                    hint: '+20 123 456 7890',
                    icon: Icons.phone_outlined),
              ],
              FormFieldBox(
                  controller: emailController,
                  label: 'Email Address',
                  hint: 'your@email.com',
                  icon: Icons.mail_outline),
              FormFieldBox(
                  controller: passwordController,
                  label: 'Password',
                  hint: 'Enter password',
                  icon: Icons.lock_outline,
                  obscure: true),
              if (!signUp)
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: () {},
                    child: const Text(
                      'Forgot Password?',
                      style: TextStyle(color: green, fontSize: 12),
                    ),
                  ),
                ),
              const SizedBox(height: 18),
              SizedBox(
                height: 54,
                child: FilledButton(
                  onPressed: submit,
                  style: FilledButton.styleFrom(
                    backgroundColor: green,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(9),
                    ),
                  ),
                  child: Text(
                    signUp ? 'Create Account' : 'Login',
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                ),
              ),
              if (!signUp) ...[
                const SizedBox(height: 28),
                Row(
                  children: const [
                    Expanded(child: Divider()),
                    Padding(
                      padding: EdgeInsets.symmetric(horizontal: 10),
                      child: Text('Or continue with',
                          style: TextStyle(color: muted, fontSize: 12)),
                    ),
                    Expanded(child: Divider()),
                  ],
                ),
                const SizedBox(height: 18),
                Row(
                  children: const [
                    Expanded(child: SocialButton(label: 'Google', icon: 'G')),
                    SizedBox(width: 10),
                    Expanded(child: SocialButton(label: 'Facebook', icon: 'f')),
                  ],
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class MenuOverlay extends StatelessWidget {
  const MenuOverlay({
    super.key,
    required this.onClose,
    required this.onGo,
  });

  final VoidCallback onClose;
  final ValueChanged<AppScreen> onGo;

  void _go(AppScreen screen) {
    onClose();
    onGo(screen);
  }

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: Material(
        color: Colors.black.withValues(alpha: .24),
        child: Stack(
          children: [
            Positioned.fill(
              child: GestureDetector(
                onTap: onClose,
                behavior: HitTestBehavior.opaque,
              ),
            ),
            TweenAnimationBuilder<double>(
              tween: Tween(begin: -1, end: 0),
              duration: const Duration(milliseconds: 260),
              curve: Curves.easeOutCubic,
              builder: (context, value, child) {
                return FractionalTranslation(
                  translation: Offset(value, 0),
                  child: child,
                );
              },
              child: GestureDetector(
                onHorizontalDragEnd: (details) {
                  if ((details.primaryVelocity ?? 0) < -220) onClose();
                },
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Container(
                    width: 306,
                    height: double.infinity,
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      boxShadow: [
                        BoxShadow(
                          color: Color(0x24000000),
                          blurRadius: 22,
                          offset: Offset(8, 0),
                        ),
                      ],
                    ),
                    child: SafeArea(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const _MapPin(
                                  icon: Icons.directions_bus,
                                  bg: green,
                                  color: Colors.white,
                                ),
                                const SizedBox(width: 12),
                                const Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        'IZEE Transit',
                                        style: TextStyle(
                                          fontWeight: FontWeight.w900,
                                          fontSize: 16,
                                        ),
                                      ),
                                      Text(
                                        'Smart City Transport',
                                        style: TextStyle(
                                          color: muted,
                                          fontSize: 12,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                IconButton(
                                  onPressed: onClose,
                                  icon: const Icon(Icons.close),
                                ),
                              ],
                            ),
                            const SizedBox(height: 28),
                            MenuItem(
                              label: 'My Trips',
                              onTap: () => _go(AppScreen.tripHistory),
                            ),
                            MenuItem(
                              label: 'Favorites',
                              onTap: () => _go(AppScreen.favorites),
                            ),
                            MenuItem(
                              label: 'Trip History',
                              onTap: () => _go(AppScreen.tripHistory),
                            ),
                            MenuItem(
                              label: 'Help & Support',
                              onTap: () => _go(AppScreen.notifications),
                            ),
                            MenuItem(
                              label: 'Settings',
                              onTap: () => _go(AppScreen.profile),
                            ),
                            const Spacer(),
                            const Text(
                              'Swipe left or tap outside to close',
                              style: TextStyle(color: muted, fontSize: 11),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.services,
    required this.connect,
    required this.onOpenMenu,
    required this.onGo,
    required this.onRouteSelected,
    required this.selectedRoute,
  });

  final AppServices services;
  final BackendConnector connect;
  final VoidCallback onOpenMenu;
  final ValueChanged<AppScreen> onGo;
  final ValueChanged<Map<String, dynamic>> onRouteSelected;
  final Map<String, dynamic>? selectedRoute;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final List<Map<String, dynamic>> liveVehicles = [];
  Timer? _refreshTimer;
  bool _loadingVehicles = true;
  String? _vehicleError;

  @override
  void initState() {
    super.initState();
    _loadLiveVehicles();
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => _loadLiveVehicles(quiet: true),
    );
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadLiveVehicles({bool quiet = false}) async {
    if (!quiet && mounted) {
      setState(() {
        _loadingVehicles = true;
        _vehicleError = null;
      });
    }

    try {
      final data = await widget.services.loadHome();
      final rawVehicles = data['data'] ?? data['vehicles'] ?? data['results'];
      final parsed = rawVehicles is List
          ? rawVehicles.whereType<Map<String, dynamic>>().toList()
          : <Map<String, dynamic>>[];

      if (!mounted) return;
      setState(() {
        liveVehicles
          ..clear()
          ..addAll(parsed);
        _loadingVehicles = false;
        _vehicleError = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _loadingVehicles = false;
        _vehicleError = error.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Column(
          children: [
            Container(
              color: green,
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
              child: SafeArea(
                bottom: false,
                child: Column(
                  children: [
                    Row(
                      children: [
                        IconButton(
                          onPressed: widget.onOpenMenu,
                          icon: const Icon(Icons.menu, color: Colors.white),
                        ),
                        const Spacer(),
                        const Text(
                          'IZEE',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const Spacer(),
                        Stack(
                          clipBehavior: Clip.none,
                          children: [
                            IconButton(
                              onPressed: () => widget.onGo(AppScreen.notifications),
                              icon: const Icon(
                                Icons.notifications_none,
                                color: Colors.white,
                              ),
                            ),
                            Positioned(
                              top: 4,
                              right: 6,
                              child: _Badge(text: '3'),
                            ),
                          ],
                        ),
                      ],
                    ),
                    _SearchBox(
                      hint: 'Where do you want to go?',
                      onTap: () => widget.onGo(AppScreen.planTrip),
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: Stack(
                children: [
                  Positioned.fill(
                    child: RouteMapPreview(
                      route: widget.selectedRoute,
                      liveVehicles: liveVehicles,
                    ),
                  ),
                  Positioned(
                    top: 18,
                    right: 16,
                    child: _CircleButton(
                      icon: Icons.my_location,
                      color: green,
                      onTap: () {},
                    ),
                  ),
                  Positioned(
                    bottom: 136,
                    left: 0,
                    right: 0,
                    child: Center(
                      child: FloatingActionButton.small(
                        heroTag: 'locate',
                        backgroundColor: green,
                        foregroundColor: Colors.white,
                        onPressed: () {},
                        child: const Icon(Icons.navigation),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        Align(
          alignment: Alignment.bottomCenter,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.fromLTRB(12, 14, 12, 10),
                decoration: const BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
                  boxShadow: [
                    BoxShadow(
                      color: Color(0x22000000),
                      blurRadius: 18,
                      offset: Offset(0, -7),
                    ),
                  ],
                ),
                child: Column(
                  children: [
                    Row(
                      children: [
                        const Text(
                          'Nearby Buses',
                          style: TextStyle(fontWeight: FontWeight.w800),
                        ),
                        const Spacer(),
                        Text(
                          _loadingVehicles
                              ? 'loading'
                              : '${liveVehicles.length} live',
                          style: const TextStyle(color: muted, fontSize: 12),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    if (_loadingVehicles)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 18),
                        child: Center(child: CircularProgressIndicator()),
                      )
                    else if (_vehicleError != null)
                      LiveVehicleEmptyState(
                        message:
                            'Cannot load live vehicles. Check backend and adb reverse.',
                        onRetry: () => _loadLiveVehicles(),
                      )
                    else if (liveVehicles.isEmpty)
                      LiveVehicleEmptyState(
                        message:
                            'No live driver vehicles yet. Start Trip in the driver app.',
                        onRetry: () => _loadLiveVehicles(),
                      )
                    else
                      ...liveVehicles.take(3).map(
                            (vehicle) => BusTile(
                              route: _vehicleTitle(vehicle),
                              place: _vehiclePlace(vehicle),
                              time: _vehicleFreshness(vehicle),
                              distance: _vehicleCoordinates(vehicle),
                              seats: 'Live',
                              onTap: () async {
                                final routeId = vehicle['route_id']?.toString();
                                if (routeId != null &&
                                    routeId.isNotEmpty &&
                                    routeId != 'null') {
                                  widget.onRouteSelected({
                                    'route_id': routeId,
                                    'route_name': vehicle['route_name'] ??
                                        vehicle['route_label'] ??
                                        routeId,
                                    'legs': [
                                      {
                                        'mode': 'bus',
                                        'route_id': routeId,
                                        'route_label':
                                            vehicle['route_name'] ?? routeId,
                                      }
                                    ],
                                  });
                                }
                                widget.onGo(AppScreen.routeDetails);
                              },
                            ),
                          ),
                  ],
                ),
              ),
              BottomNav(current: AppScreen.home, onGo: widget.onGo),
            ],
          ),
        ),
      ],
    );
  }

  String _vehicleTitle(Map<String, dynamic> vehicle) {
    return vehicle['vehicle_id']?.toString() ?? 'Live vehicle';
  }

  String _vehiclePlace(Map<String, dynamic> vehicle) {
    return 'Driver location update';
  }

  String _vehicleCoordinates(Map<String, dynamic> vehicle) {
    final lat = _asDouble(vehicle['lat']);
    final lon = _asDouble(vehicle['lon']);
    if (lat == null || lon == null) return 'GPS';
    return '${lat.toStringAsFixed(4)}, ${lon.toStringAsFixed(4)}';
  }

  String _vehicleFreshness(Map<String, dynamic> vehicle) {
    final raw = vehicle['last_update']?.toString();
    if (raw == null || raw.isEmpty) return 'live';
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return 'live';
    final minutes = DateTime.now().toUtc().difference(parsed.toUtc()).inMinutes;
    if (minutes <= 0) return 'now';
    if (minutes < 60) return '$minutes min';
    return '${minutes ~/ 60}h';
  }

  double? _asDouble(Object? value) {
    if (value is num) return value.toDouble();
    if (value == null) return null;
    return double.tryParse(value.toString());
  }
}

class LiveVehicleEmptyState extends StatelessWidget {
  const LiveVehicleEmptyState({
    super.key,
    required this.message,
    required this.onRetry,
  });

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: softLine),
      ),
      child: Row(
        children: [
          const Icon(Icons.directions_bus, color: muted),
          const SizedBox(width: 10),
          Expanded(
            child: Text(message, style: const TextStyle(color: muted)),
          ),
          IconButton(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, color: green),
            tooltip: 'Refresh live vehicles',
          ),
        ],
      ),
    );
  }
}

class PlanTripScreen extends StatefulWidget {
  const PlanTripScreen({
    super.key,
    required this.services,
    required this.connect,
    required this.onGo,
    required this.session,
    required this.onRouteSelected,
  });

  final AppServices services;
  final BackendConnector connect;
  final ValueChanged<AppScreen> onGo;
  final PlanTripSession session;
  final ValueChanged<Map<String, dynamic>> onRouteSelected;

  @override
  State<PlanTripScreen> createState() => _PlanTripScreenState();
}

class _PlanTripScreenState extends State<PlanTripScreen> {
  late final TextEditingController _originController;
  late final TextEditingController _destinationController;
  late final FocusNode _originFocusNode;
  late final FocusNode _destinationFocusNode;
  Timer? _originDebounce;
  Timer? _destinationDebounce;
  List<Map<String, dynamic>> _originSuggestions = const [];
  List<Map<String, dynamic>> _destinationSuggestions = const [];
  bool _searchingOrigin = false;
  bool _searchingDestination = false;
  bool _originNoResults = false;
  bool _destinationNoResults = false;
  bool _suppressSuggestionLookup = false;
  bool _locatingOrigin = false;
  int _originSuggestionRequest = 0;
  int _destinationSuggestionRequest = 0;

  @override
  void initState() {
    super.initState();
    _originController = TextEditingController(text: widget.session.originText);
    _destinationController =
        TextEditingController(text: widget.session.destinationText);
    _originFocusNode = FocusNode();
    _destinationFocusNode = FocusNode();
    _originController.addListener(() => _queueSuggestions(forOrigin: true));
    _destinationController
        .addListener(() => _queueSuggestions(forOrigin: false));
    _originFocusNode.addListener(_handleFieldFocusChanged);
    _destinationFocusNode.addListener(_handleFieldFocusChanged);
  }

  @override
  void dispose() {
    _originDebounce?.cancel();
    _destinationDebounce?.cancel();
    _originFocusNode.removeListener(_handleFieldFocusChanged);
    _destinationFocusNode.removeListener(_handleFieldFocusChanged);
    _originFocusNode.dispose();
    _destinationFocusNode.dispose();
    _originController.dispose();
    _destinationController.dispose();
    super.dispose();
  }

  void _handleFieldFocusChanged() {
    if (!mounted) return;
    setState(() {
      if (_originFocusNode.hasFocus) {
        _destinationSuggestions = const [];
        _destinationNoResults = false;
      } else if (_destinationFocusNode.hasFocus) {
        _originSuggestions = const [];
        _originNoResults = false;
      }
    });
  }

  Future<Map<String, dynamic>> _searchRoutes() async {
    final origin = await _coordinatesFor(
      selected: widget.session.selectedOrigin,
      text: _originController.text,
      fieldName: 'origin',
    );
    final destination = await _coordinatesFor(
  int _destinationSuggestionRequest = 0;

  @override
  void initState() {
    super.initState();
    _originController = TextEditingController(text: widget.session.originText);
    _destinationController =
        TextEditingController(text: widget.session.destinationText);
    _originFocusNode = FocusNode();
    _destinationFocusNode = FocusNode();
    _originController.addListener(() => _queueSuggestions(forOrigin: true));
    _destinationController
        .addListener(() => _queueSuggestions(forOrigin: false));
    _originFocusNode.addListener(_handleFieldFocusChanged);
    _destinationFocusNode.addListener(_handleFieldFocusChanged);
  }

  @override
  void dispose() {
    _originDebounce?.cancel();
    _destinationDebounce?.cancel();
    _originFocusNode.removeListener(_handleFieldFocusChanged);
    _destinationFocusNode.removeListener(_handleFieldFocusChanged);
    _originFocusNode.dispose();
    _destinationFocusNode.dispose();
    _originController.dispose();
    _destinationController.dispose();
    super.dispose();
  }

  void _handleFieldFocusChanged() {
    if (!mounted) return;
    setState(() {
      if (_originFocusNode.hasFocus) {
        _destinationSuggestions = const [];
        _destinationNoResults = false;
      } else if (_destinationFocusNode.hasFocus) {
        _originSuggestions = const [];
        _originNoResults = false;
      }
    });
  }

  Future<Map<String, dynamic>> _searchRoutes() async {
    final origin = await _coordinatesFor(
      selected: widget.session.selectedOrigin,
      text: _originController.text,
      fieldName: 'origin',
    );
    final destination = await _coordinatesFor(
      selected: widget.session.selectedDestination,
      text: _destinationController.text,
      fieldName: 'destination',
    );

    widget.session.selectedOrigin = origin;
    widget.session.selectedDestination = destination;

    return widget.services.calculateRouteFromCoordinates(
      origin: origin,
      destination: destination,
      departureTime: widget.session.selectedDepartureTime,
    );
  }

  Future<void> _submitSearch() async {
    _originDebounce?.cancel();
    _destinationDebounce?.cancel();
    setState(() {
      widget.session.errorMessage = null;
      widget.session.loadingRoutes = true;
      widget.session.lastSearchRequest =
          '${_originController.text.trim()} -> ${_destinationController.text.trim()}';
      _originSuggestions = const [];
      _destinationSuggestions = const [];
    });

    try {
      final response = await _searchRoutes();
      if (!mounted) return;
      setState(() {
        widget.session.routeResponse = response;
        widget.session.loadingRoutes = false;
        _saveRecentSearch();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        widget.session.errorMessage = _friendlySearchError(error);
        widget.session.loadingRoutes = false;
      });
    }
  }

  Future<void> _pickTime() async {
    final TimeOfDay? picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
      builder: (context, child) {
        return Theme(
          data: ThemeData.light().copyWith(
            colorScheme: const ColorScheme.light(
              primary: green,
              onPrimary: Colors.white,
              onSurface: ink,
            ),
          ),
          child: child!,
        );
      },
    );
    if (picked != null) {
      setState(() {
        final hh = picked.hour.toString().padLeft(2, '0');
        final mm = picked.minute.toString().padLeft(2, '0');
        widget.session.selectedDepartureTime = '$hh:$mm:00';
      });
    }
  }

  Future<void> _useCurrentLocationAsOrigin() async {
    if (_locatingOrigin) return;

    setState(() {
      _locatingOrigin = true;
      widget.session.errorMessage = null;
      _originSuggestions = const [];
      _originNoResults = false;
    });

    try {
      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        throw Exception('Turn on location services on your phone first.');
      }

      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (permission == LocationPermission.denied) {
        throw Exception('Location permission is required to use your location.');
      }

      if (permission == LocationPermission.deniedForever) {
        throw Exception(
          'Location permission is permanently denied. Enable it from app settings.',
        );
      }

      final position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );
      const label = 'My current location';
      final coordinates = {
        'lat': position.latitude,
        'lon': position.longitude,
      };

      _originDebounce?.cancel();
      _suppressSuggestionLookup = true;
      _originController.text = label;
      _originController.selection = TextSelection.collapsed(
        offset: label.length,
      );
      _suppressSuggestionLookup = false;
      _originFocusNode.unfocus();

      if (!mounted) return;
      setState(() {
        widget.session.originText = label;
        widget.session.selectedOrigin = coordinates;
        widget.session.errorMessage = null;
        _originSuggestions = const [];
        _originNoResults = false;
        _locatingOrigin = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        widget.session.errorMessage = error.toString().replaceFirst(
              'Exception: ',
              '',
            );
        _locatingOrigin = false;
      });
    }
  }

  Future<void> _runRecentSearch(RecentTripSearch recent) async {
    _originDebounce?.cancel();
    _destinationDebounce?.cancel();
    _suppressSuggestionLookup = true;
    _originController.text = recent.originText;
    _destinationController.text = recent.destinationText;
    _originController.selection =
        TextSelection.collapsed(offset: recent.originText.length);
    _destinationController.selection =
        TextSelection.collapsed(offset: recent.destinationText.length);
    _suppressSuggestionLookup = false;

    setState(() {
      widget.session.originText = recent.originText;
      widget.session.destinationText = recent.destinationText;
      widget.session.selectedOrigin = Map<String, double>.from(recent.origin);
      widget.session.selectedDestination =
          Map<String, double>.from(recent.destination);
      widget.session.errorMessage = null;
      widget.session.loadingRoutes = true;
      widget.session.lastSearchRequest = recent.label;
      _originSuggestions = const [];
      _destinationSuggestions = const [];
      _originNoResults = false;
      _destinationNoResults = false;
    });

    try {
      final response = await _searchRoutes();
      if (!mounted) return;
      setState(() {
        widget.session.routeResponse = response;
        widget.session.loadingRoutes = false;
        _saveRecentSearch();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        widget.session.errorMessage = _friendlySearchError(error);
        widget.session.loadingRoutes = false;
      });
    }
  }

  void _saveRecentSearch() {
    final origin = widget.session.selectedOrigin;
    final destination = widget.session.selectedDestination;
    final originText = _originController.text.trim();
    final destinationText = _destinationController.text.trim();

    if (origin == null ||
        destination == null ||
        originText.isEmpty ||
        destinationText.isEmpty) {
      return;
    }

    widget.session.recentSearches.removeWhere(
      (item) =>
          item.originText.toLowerCase() == originText.toLowerCase() &&
          item.destinationText.toLowerCase() == destinationText.toLowerCase(),
    );
    widget.session.recentSearches.insert(
      0,
      RecentTripSearch(
        originText: originText,
        destinationText: destinationText,
        origin: Map<String, double>.from(origin),
        destination: Map<String, double>.from(destination),
      ),
    );

    if (widget.session.recentSearches.length > 5) {
      widget.session.recentSearches.removeRange(
        5,
        widget.session.recentSearches.length,
      );
    }
  }

  Future<Map<String, double>> _coordinatesFor({
    required Map<String, double>? selected,
    required String text,
    required String fieldName,
  }) async {
    if (selected != null) return selected;

    final query = text.trim();
    if (query.length < 2) {
      throw Exception('Select a $fieldName place first.');
    }

    final places = await _searchPlaces(query);
    if (places.isEmpty) {
      throw Exception('geocode:$fieldName');
    }

    return _placeCoordinates(places.first);
  }

  void _queueSuggestions({required bool forOrigin}) {
    if (_suppressSuggestionLookup) return;
    if (forOrigin) {
      widget.session.originText = _originController.text;
      widget.session.selectedOrigin = null;
    } else {
      widget.session.destinationText = _destinationController.text;
      widget.session.selectedDestination = null;
    }
    final debounce = forOrigin ? _originDebounce : _destinationDebounce;
    debounce?.cancel();
    final nextDebounce = Timer(const Duration(milliseconds: 400), () {
      _loadSuggestions(forOrigin: forOrigin);
    });
    if (forOrigin) {
      _originDebounce = nextDebounce;
    } else {
      _destinationDebounce = nextDebounce;
    }
  }

  Future<void> _loadSuggestions({required bool forOrigin}) async {
    final query =
        (forOrigin ? _originController.text : _destinationController.text)
            .trim();
    final requestId = forOrigin
        ? ++_originSuggestionRequest
        : ++_destinationSuggestionRequest;

    if (query.length < 2) {
      if (!mounted) return;
      setState(() {
        if (forOrigin) {
          _originSuggestions = const [];
          _searchingOrigin = false;
          _originNoResults = false;
        } else {
          _destinationSuggestions = const [];
          _searchingDestination = false;
          _destinationNoResults = false;
        }
      });
      return;
    }

    setState(() {
      if (forOrigin) {
        _searchingOrigin = true;
      } else {
        _searchingDestination = true;
      }
    });

    try {
      final suggestions = await _searchPlaces(query);
      if (!mounted) return;
      final isLatest = forOrigin
          ? requestId == _originSuggestionRequest
          : requestId == _destinationSuggestionRequest;
      if (!isLatest) return;
      final stillCurrent = query ==
          (forOrigin ? _originController.text : _destinationController.text)
              .trim();
      if (!stillCurrent) return;

      setState(() {
        if (forOrigin) {
          _originSuggestions = suggestions.take(4).toList();
          _searchingOrigin = false;
          _originNoResults = suggestions.isEmpty;
        } else {
          _destinationSuggestions = suggestions.take(4).toList();
          _searchingDestination = false;
          _destinationNoResults = suggestions.isEmpty;
        }
      });
    } catch (error) {
      if (!mounted) return;
      final isLatest = forOrigin
          ? requestId == _originSuggestionRequest
          : requestId == _destinationSuggestionRequest;
      if (!isLatest) return;
      setState(() {
        widget.session.errorMessage =
            _friendlySuggestionError(query: query, error: error);
        if (forOrigin) {
          _originSuggestions = const [];
          _searchingOrigin = false;
          _originNoResults = false;
        } else {
          _destinationSuggestions = const [];
          _searchingDestination = false;
          _destinationNoResults = false;
        }
      });
    }
  }

  Future<List<Map<String, dynamic>>> _searchPlaces(String query) async {
    final normalized = query.trim().toLowerCase();
    final cached = widget.session.geocodeCache[normalized];
    if (cached != null && cached.isNotEmpty) return cached;

    final places = await widget.services.searchPlaces(query);
    if (places.isNotEmpty) {
      widget.session.geocodeCache[normalized] = places;
    } else {
      widget.session.geocodeCache.remove(normalized);
    }
    return places;
  }

  void _selectSuggestion({
    required bool forOrigin,
    required Map<String, dynamic> place,
  }) {
    final name = _placeName(place);
    final coordinates = _placeCoordinates(place);
    final controller = forOrigin ? _originController : _destinationController;
    _suppressSuggestionLookup = true;
    controller.text = name;
    controller.selection = TextSelection.collapsed(offset: name.length);
    _suppressSuggestionLookup = false;

    setState(() {
      widget.session.errorMessage = null;
      if (forOrigin) {
        _originSuggestions = const [];
        _originNoResults = false;
        _originFocusNode.unfocus();
        widget.session.originText = name;
        widget.session.selectedOrigin = coordinates;
      } else {
        _destinationSuggestions = const [];
        _destinationNoResults = false;
        _destinationFocusNode.unfocus();
        widget.session.destinationText = name;
        widget.session.selectedDestination = coordinates;
      }
    });
  }

  String _friendlySearchError(Object error) {
    final message = error.toString();
    if (message.contains('geocode:') ||
        message.contains('No geocoding results')) {
      return 'Could not find this place. Please select a suggestion.';
    }
    if (message.contains('Select a')) {
      return message.replaceFirst('Exception: ', '');
    }
    if (message.contains('SocketException') ||
        message.contains('ClientException') ||
        message.contains('TimeoutException') ||
        message.contains('Failed host lookup') ||
        message.contains('Connection refused')) {
      return 'Cannot reach backend at ${ApiConfig.baseUrl}. Check FastAPI server and adb reverse.';
    }
    return message.replaceFirst('Exception: ', '');
  }

  String _friendlySuggestionError({
    required String query,
    required Object error,
  }) {
    final message = error.toString();
    if (message.contains('SocketException') ||
        message.contains('ClientException') ||
        message.contains('TimeoutException') ||
        message.contains('Failed host lookup') ||
        message.contains('Connection refused')) {
      return 'Cannot reach backend at ${ApiConfig.baseUrl}. Check FastAPI server and adb reverse.';
    }
    return 'Could not load place suggestions for "$query": ${message.replaceFirst('Exception: ', '')}';
  }

  String _placeName(Map<String, dynamic> place) {
    final name = place['name'] ?? place['display_name'] ?? place['label'];
    return name?.toString().split(',').first.trim() ?? 'Selected place';
  }

  Map<String, double> _placeCoordinates(Map<String, dynamic> place) {
    return {
      'lat': _toDouble(place['lat']),
      'lon': _toDouble(place['lon']),
    };
  }

  double _toDouble(Object? value) {
    if (value is num) return value.toDouble();
    return double.parse(value.toString());
  }

  @override
  Widget build(BuildContext context) {
    final focusedContext = FocusManager.instance.primaryFocus?.context;
    final keyboardVisible = MediaQuery.viewInsetsOf(context).bottom > 0 ||
        focusedContext?.widget is EditableText;
    final showOriginSuggestions =
        !keyboardVisible || _originFocusNode.hasFocus;
    final showDestinationSuggestions =
        !keyboardVisible || _destinationFocusNode.hasFocus;
    final recentSearches = widget.session.recentSearches;
    final searchFocused =
        _originFocusNode.hasFocus || _destinationFocusNode.hasFocus;
    final searchOnlyMode = keyboardVisible && searchFocused;
    final header = GreenHeader(
      title: 'Plan Your Trip',
      onBack: () => widget.onGo(AppScreen.home),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          LocationField(
            icon: Icons.navigation_outlined,
            controller: _originController,
            focusNode: _originFocusNode,
            trailing: IconButton(
              tooltip: 'Use my location',
              onPressed: _locatingOrigin ? null : _useCurrentLocationAsOrigin,
              icon: _locatingOrigin
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.my_location, color: green),
            ),
            onSubmitted: (_) => _submitSearch(),
          ),
          if (showOriginSuggestions)
            _responsiveSuggestions(
              keyboardVisible: keyboardVisible,
              visibleSuggestionCount: _originSuggestions.length,
              child: PlaceSuggestions(
                places: _originSuggestions,
                loading: _searchingOrigin,
                noResults: _originNoResults,
                scrollable: keyboardVisible,
                onSelect: (place) =>
                    _selectSuggestion(forOrigin: true, place: place),
              ),
            ),
          SizedBox(height: keyboardVisible ? 8 : 12),
          LocationField(
            icon: Icons.location_on_outlined,
            controller: _destinationController,
            focusNode: _destinationFocusNode,
            red: true,
            onSubmitted: (_) => _submitSearch(),
          ),
          if (showDestinationSuggestions)
            _responsiveSuggestions(
              keyboardVisible: keyboardVisible,
              visibleSuggestionCount: _destinationSuggestions.length,
              child: PlaceSuggestions(
                places: _destinationSuggestions,
                loading: _searchingDestination,
                noResults: _destinationNoResults,
                scrollable: keyboardVisible,
                red: true,
                onSelect: (place) =>
                    _selectSuggestion(forOrigin: false, place: place),
              ),
            ),
          SizedBox(height: keyboardVisible ? 8 : 12),
          Row(
            children: [
              Expanded(
                child: _ModeChip(
                  icon: Icons.schedule, 
                  label: 'Leave now',
                  selected: widget.session.selectedDepartureTime == 'now',
                  onTap: () {
                    setState(() {
                      widget.session.selectedDepartureTime = 'now';
                    });
                  },
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _ModeChip(
                  icon: Icons.calendar_month, 
                  label: widget.session.selectedDepartureTime == 'now' ? 'Schedule' : widget.session.selectedDepartureTime.substring(0, 5),
                  selected: widget.session.selectedDepartureTime != 'now',
                  onTap: _pickTime,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: FilledButton.icon(
                  onPressed: widget.session.loadingRoutes ? null : _submitSearch,
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: green,
                    disabledBackgroundColor:
                        Colors.white.withValues(alpha: .72),
                    disabledForegroundColor: green.withValues(alpha: .45),
                  ),
                  icon: widget.session.loadingRoutes
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.search, size: 18),
                  label: const FittedBox(child: Text('Search')),
                ),
              ),
            ],
          ),
        ],
      ),
    );

    if (searchOnlyMode) {
      return ListView(
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom + 16,
        ),
        children: [header],
      );
    }

    return Column(
      children: [
        header,
        Expanded(
          child: widget.session.routeResponse == null &&
                  !widget.session.loadingRoutes
              ? ListView(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  padding: EdgeInsets.fromLTRB(
                    18,
                    22,
                    18,
                    MediaQuery.viewInsetsOf(context).bottom > 0 ? 26 : 18,
                  ),
                  children: [
                    const SectionTitle(
                      title: 'Suggested Routes',
                      trailing: 'search',
                    ),
                    if (widget.session.errorMessage != null) ...[
                      const SizedBox(height: 10),
                      Text(
                        widget.session.errorMessage!,
                        style: const TextStyle(color: rose, fontSize: 12),
                      ),
                    ],
                    const SizedBox(height: 24),
                    const EmptyRouteState(),
                  ],
                )
              : Builder(
                  builder: (context) {
                    final routeCards =
                        _buildRouteCards(widget.session.routeResponse);
                    final hasBackendRoutes = routeCards.isNotEmpty;

                    return ListView(
                      keyboardDismissBehavior:
                          ScrollViewKeyboardDismissBehavior.onDrag,
                      padding: EdgeInsets.fromLTRB(
                        18,
                        22,
                        18,
                        MediaQuery.viewInsetsOf(context).bottom > 0 ? 26 : 18,
                      ),
                      children: [
                        SectionTitle(
                          title: 'Suggested Routes',
                          trailing: hasBackendRoutes
                              ? '${routeCards.length} options'
                              : widget.session.loadingRoutes
                                  ? 'loading'
                                  : '0 options',
                        ),
                        if (widget.session.errorMessage != null) ...[
                          const SizedBox(height: 10),
                          Text(
                            widget.session.errorMessage!,
                            style: const TextStyle(color: rose, fontSize: 12),
                          ),
                        ],
                        if (widget.session.errorMessage == null &&
                            !widget.session.loadingRoutes &&
                            !hasBackendRoutes) ...[
                          const SizedBox(height: 10),
                          Text(
                            widget.session.routeResponse?['message']
                                    ?.toString() ??
                                'No backend route alternatives returned for these places.',
                            style: const TextStyle(color: muted, fontSize: 12),
                          ),
                        ],
                        const SizedBox(height: 12),
                        if (widget.session.loadingRoutes) ...[
                          const SizedBox(height: 30),
                          const Center(child: CircularProgressIndicator()),
                        ] else ...[
                          for (int i = 0; i < routeCards.length; i++)
                            RouteCard(
                              chips: routeCards[i].chips,
                              tag: routeCards[i].tag,
                              minutes: routeCards[i].minutes,
                              transfer: routeCards[i].transfer,
                              walking: routeCards[i].walking,
                              arrival: routeCards[i].arrival,
                              price: routeCards[i].price,
                              badges: routeCards[i].badges,
                              steps: routeCards[i].steps,
                              depart: routeCards[i].depart,
                              selected: i == 0,
                              onTap: () {
                                final rawRoute = routeCards[i].rawRoute;
                                if (rawRoute != null) {
                                  widget.onRouteSelected(rawRoute);
                                  widget.onGo(AppScreen.routeDetails);
                                }
                              },
                            ),
                          const SizedBox(height: 22),
                          const Text(
                            'Recent Searches',
                            style: TextStyle(
                                color: muted, fontWeight: FontWeight.w800),
                          ),
                          const SizedBox(height: 12),
                          if (recentSearches.isEmpty)
                            const Text(
                              'Search routes to build your recent list.',
                              style: TextStyle(color: muted, fontSize: 12),
                            )
                          else
                            ...recentSearches.map(
                              (item) => RecentSearch(
                                text: item.label,
                                onTap: () => _runRecentSearch(item),
                              ),
                            ),
                        ],
                      ],
                    );
                  },
                ),
          ),
      ],
    );
  }

  Widget _responsiveSuggestions({
    required bool keyboardVisible,
    required int visibleSuggestionCount,
    required Widget child,
  }) {
    final maxHeight = keyboardVisible
        ? (visibleSuggestionCount <= 2 ? 116.0 : 148.0)
        : 240.0;
    return ConstrainedBox(
      constraints: BoxConstraints(maxHeight: maxHeight),
      child: child,
    );
  }

  List<RouteCardData> _buildRouteCards(Map<String, dynamic>? data) {
    final routes = data?['routes'];
    if (routes is! List) return const [];

    return routes
        .whereType<Map<String, dynamic>>()
        .map(_routeCardFromBackend)
        .toList();
  }

  RouteCardData _routeCardFromBackend(Map<String, dynamic> route) {
    final legs = (route['legs'] as List?)?.whereType<Map<String, dynamic>>() ??
        const Iterable<Map<String, dynamic>>.empty();
    final routeChips = legs
        .map(_routeChip)
        .where((chip) => chip.label.isNotEmpty && chip.label != 'null')
        .toList();
    final uniqueRouteChips = <RouteChipData>[];
    for (final chip in routeChips) {
      if (!uniqueRouteChips.any((item) => item.label == chip.label)) {
        uniqueRouteChips.add(chip);
      }
    }
    final steps = legs.map(_legStep).whereType<RouteLegData>().toList();
    final minutes = ((route['total_travel_time'] as num? ?? 0) / 60).round();
    final transferCount = route['transfer_count'] as num? ?? 0;
    final walkingMinutes =
        ((route['total_walking_time'] as num? ?? 0) / 60).round();
    final fare = route['total_fare'] ?? route['fare']?['total_fare'];

    return RouteCardData(
      chips: uniqueRouteChips.isEmpty
          ? const [RouteChipData(label: 'Route', mode: 'bus')]
          : uniqueRouteChips.take(3).toList(),
      tag: _alternativeLabel(route),
      badges: _alternativeBadges(route),
      minutes: '${minutes == 0 ? '--' : minutes} min',
      transfer:
          '${transferCount.round()} transfer${transferCount == 1 ? '' : 's'}',
      walking: '$walkingMinutes min walk',
      arrival: 'Arrives ${route['estimated_arrival_time'] ?? '--'}',
      price: fare == null ? 'Fare --' : '${_formatMoney(fare)} EGP',
      steps: steps.isEmpty
          ? const [
              RouteLegData(
                mode: 'route',
                title: 'Backend route returned',
                detail: 'No leg details were included in the response',
              )
            ]
          : steps,
      depart:
          'Mode summary from ${steps.length} backend leg${steps.length == 1 ? '' : 's'}',
      rawRoute: route,
    );
  }

  RouteChipData _routeChip(Map<String, dynamic> leg) {
    final mode = (leg['mode'] ?? '').toString();
    final label = leg['route_label'] ?? leg['route_id'] ?? labelForMode(mode);
    return RouteChipData(
        label: _compactRouteLabel(label.toString()), mode: mode);
  }

  RouteLegData? _legStep(Map<String, dynamic> leg) {
    final from = leg['from_stop'];
    final to = leg['to_stop'];
    final fromName = from is Map
        ? (from['name'] ?? from['stop_name'] ?? from['stop_id'])
        : null;
    final toName =
        to is Map ? (to['name'] ?? to['stop_name'] ?? to['stop_id']) : null;
    final label =
        leg['route_label'] ?? leg['route_id'] ?? leg['mode'] ?? 'Route';
    final mode = (leg['mode'] ?? '').toString();
    final seconds = leg['travel_time'] as num?;
    final minutes = seconds == null ? null : (seconds / 60).round();

    if (fromName == null || toName == null) return null;
    return RouteLegData(
      mode: mode,
      title: '${labelForMode(mode)} - ${_compactRouteLabel(label.toString())}',
      detail:
          '${_shortName(fromName.toString())} -> ${_shortName(toName.toString())}${minutes == null ? '' : ' ($minutes min)'}',
    );
  }

  String _compactRouteLabel(String value) {
    final clean = value.trim();
    if (clean.length <= 12) return clean;
    final parts = clean.split(RegExp(r'\s+-\s+'));
    if (parts.length > 1) {
      return '${_shortName(parts.first)} - ${_shortName(parts.last)}';
    }
    return '${clean.substring(0, 11)}...';
  }

  String _alternativeLabel(Map<String, dynamic> route) {
    final raw = route['ranking_type'] ??
        route['alternative_type'] ??
        route['label'] ??
        _primaryBadge(route) ??
        'recommended';
    return _mapAlternativeText(raw.toString());
  }

  List<String> _alternativeBadges(Map<String, dynamic> route) {
    final labels = <String>[];
    labels.add(_alternativeLabel(route));

    final badges = route['badges'];
    if (badges is List) {
      for (final badge in badges) {
        final label = _mapAlternativeText(badge.toString());
        if (!labels.contains(label)) labels.add(label);
      }
    }

    return labels.take(3).toList();
  }

  String _mapAlternativeText(String value) {
    final clean = value.replaceAll('_', ' ').trim().toLowerCase();

    if (clean.contains('fewest') && clean.contains('transfer')) {
      return 'Fewest transfers';
    }
    if (clean.contains('least') && clean.contains('walking')) {
      return 'Least walking';
    }
    if (clean.contains('fastest')) return 'Fastest';
    if (clean.contains('cheapest')) return 'Cheapest';
    if (clean.contains('best balance')) return 'Recommended';
    if (clean.contains('recommended')) return 'Recommended';
    if (clean == 'walk only') return 'Walk only';

    final titled = clean
        .split(RegExp(r'\s+'))
        .where((word) => word.isNotEmpty)
        .map((word) => '${word[0].toUpperCase()}${word.substring(1)}')
        .join(' ');
    return titled.length <= 18 ? titled : '${titled.substring(0, 17)}...';
  }

  Object? _primaryBadge(Map<String, dynamic> route) {
    final badges = route['badges'];
    if (badges is List && badges.isNotEmpty) return badges.first;
    return null;
  }

  String _shortName(String value) {
    final clean = value.trim().replaceAll(RegExp(r'\s*\([^)]*\)'), '');
    return clean.length <= 24 ? clean : '${clean.substring(0, 23)}...';
  }

  String _formatMoney(Object? value) {
    if (value is num) {
      return value % 1 == 0
          ? value.toInt().toString()
          : value.toStringAsFixed(1);
    }
    return value?.toString() ?? '0';
  }
}

class _ModeChip extends StatelessWidget {
  const _ModeChip({required this.icon, required this.label, this.selected = false, this.onTap});

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(9),
      child: Container(
        height: 44,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        decoration: BoxDecoration(
            color: selected ? Colors.white : Colors.white.withValues(alpha: .2),
            borderRadius: BorderRadius.circular(9)),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: selected ? green : Colors.white, size: 16),
            const SizedBox(width: 6),
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                child: Text(label,
                    maxLines: 1,
                    style: TextStyle(
                        color: selected ? green : Colors.white, fontWeight: FontWeight.w800)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class RouteCardData {
  const RouteCardData({
    required this.chips,
    required this.tag,
    required this.minutes,
    required this.transfer,
    required this.walking,
    required this.arrival,
    required this.price,
    required this.badges,
    required this.steps,
    required this.depart,
    this.rawRoute,
  });

  final List<RouteChipData> chips;
  final String tag;
  final String minutes;
  final String transfer;
  final String walking;
  final String arrival;
  final String price;
  final List<String> badges;
  final List<RouteLegData> steps;
  final String depart;
  final Map<String, dynamic>? rawRoute;
}

class RouteChipData {
  const RouteChipData({required this.label, required this.mode});

  final String label;
  final String mode;
}

class RouteLegData {
  const RouteLegData({
    required this.mode,
    required this.title,
    required this.detail,
  });

  final String mode;
  final String title;
  final String detail;
}

class EmptyRouteState extends StatelessWidget {
  const EmptyRouteState({super.key});

  @override
  Widget build(BuildContext context) {
    return CardShell(
      padding: const EdgeInsets.all(18),
      child: Row(
        children: const [
          _MapPin(icon: Icons.search, bg: paleGreen, color: green),
          SizedBox(width: 12),
          Expanded(
            child: Text(
              'Search and select origin and destination places to load real backend route alternatives.',
              style: TextStyle(color: muted, height: 1.4),
            ),
          ),
        ],
      ),
    );
  }
}

class RouteDetailsScreen extends StatefulWidget {
  const RouteDetailsScreen({
    super.key,
    required this.services,
    required this.connect,
    required this.onGo,
    required this.route,
  });

  final AppServices services;
  final BackendConnector connect;
  final ValueChanged<AppScreen> onGo;
  final Map<String, dynamic>? route;

  @override
  State<RouteDetailsScreen> createState() => _RouteDetailsScreenState();
}

class _RouteDetailsScreenState extends State<RouteDetailsScreen> {
  final Map<String, Map<String, dynamic>> _vehiclesById = {};
  Timer? _trackingTimer;
  bool _trackingLoading = false;
  bool _navigationStarted = false;
  String? _trackingMessage;
  Map<String, dynamic>? _enrichedRoute;

  /// Use enriched route data when available, falling back to widget.route.
  Map<String, dynamic>? get _effectiveRoute => _enrichedRoute ?? widget.route;

  @override
  void initState() {
    super.initState();
    _startTracking();
  }

  @override
  void didUpdateWidget(covariant RouteDetailsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_routeId(oldWidget.route) != _routeId(widget.route)) {
      _startTracking();
    }
  }

  @override
  void dispose() {
    _trackingTimer?.cancel();
    debugPrint('PASSENGER_POLL_TIMER_STOPPED');
    super.dispose();
  }

  void _startTracking() {
    debugPrint('PASSENGER_TRACKING_SCREEN_OPENED');
    final routeId = _routeId(widget.route);
    debugPrint('PASSENGER_SELECTED_ROUTE_ID: $routeId');
    _trackingTimer?.cancel();
    _vehiclesById.clear();
    _navigationStarted = false;
    _trackingMessage = null;
    _enrichedRoute = null;
    debugPrint('PASSENGER_POLL_TIMER_STARTED');
    _fetchRouteDetails();
    _pollVehicles();
    _trackingTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => _pollVehicles(quiet: true),
    );
  }

  Future<void> _fetchRouteDetails() async {
    final routeId = _routeId(widget.route);
    if (routeId == null) return;
    try {
      debugPrint('PASSENGER_FETCH_ROUTE_DETAILS: $routeId');
      final data = await widget.services.loadRouteDetails(routeId);
      if (!mounted) return;
      // The backend returns {route_id, route_name, label, total_travel_time, total_fare, legs}
      // which is exactly what the map and stops timeline need.
      final legs = data['legs'];
      if (legs is List && legs.isNotEmpty) {
        setState(() {
          _enrichedRoute = data;
        });
        debugPrint('PASSENGER_ROUTE_DETAILS_ENRICHED: ${legs.length} legs');
      }
    } catch (e) {
      debugPrint('PASSENGER_ROUTE_DETAILS_ERROR: $e');
      // Not critical – we still have widget.route as fallback
    }
  }

  Future<void> _pollVehicles({bool quiet = false}) async {
    final routeId = _routeId(_effectiveRoute);
    if (routeId == null) {
      if (mounted) {
        setState(() {
          _vehiclesById.clear();
          _trackingLoading = false;
          _trackingMessage = 'Select a route to view live vehicle tracking.';
        });
      }
      return;
    }

    if (!quiet && mounted) {
      setState(() {
        _trackingLoading = true;
        _trackingMessage = null;
      });
    }

    try {
      final url = '${ApiConfig.baseUrl}/passenger/routes/$routeId/vehicles';
      debugPrint('PASSENGER_VEHICLES_REQUEST_URL: $url');
      final data = await widget.services.loadRouteVehicles(routeId);
      final rawVehicles = data['data'] ?? data['vehicles'] ?? data['results'];
      final parsed = rawVehicles is List
          ? rawVehicles.whereType<Map<String, dynamic>>().toList()
          : <Map<String, dynamic>>[];
      debugPrint('PASSENGER_VEHICLES_RESPONSE: $parsed');

      final nextVehicles = <String, Map<String, dynamic>>{};
      var hasStale = false;
      var hasUnavailable = false;
      for (final vehicle in parsed) {
        final vehicleId = vehicle['vehicle_id']?.toString();
        if (vehicleId == null || vehicleId.isEmpty) continue;
        final status = _vehicleLocationStatus(vehicle);
        if (status == 'stale') {
          hasStale = true;
          debugPrint('PASSENGER_LOCATION_STALE: vehicle_id=$vehicleId');
        }
        if (status == 'unavailable') {
          hasUnavailable = true;
          continue;
        }
        nextVehicles[vehicleId] = vehicle;
        debugPrint('PASSENGER_MAP_MARKER_UPDATED: vehicle_id=$vehicleId');
      }

      if (!mounted) return;
      setState(() {
        _vehiclesById
          ..clear()
          ..addAll(nextVehicles);
        _trackingLoading = false;
        if (nextVehicles.isNotEmpty && hasStale) {
          _trackingMessage = 'Vehicle location is outdated.';
        } else if (nextVehicles.isEmpty && hasUnavailable) {
          _trackingMessage = 'Live vehicle location unavailable.';
        } else if (nextVehicles.isEmpty) {
          _trackingMessage =
              'No active vehicle currently available for this route.';
        } else {
          _trackingMessage = null;
        }
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _vehiclesById.clear();
        _trackingLoading = false;
        _trackingMessage = 'No active vehicle currently available for this route.';
      });
    }
  }

  String? _routeId(Map<String, dynamic>? route) {
    final direct = route?['route_id']?.toString();
    if (direct != null && direct.isNotEmpty && direct != 'null') return direct;
    final legs = route?['legs'];
    if (legs is List) {
      for (final leg in legs.whereType<Map<String, dynamic>>()) {
        final mode = (leg['mode'] ?? '').toString().toLowerCase();
        if (mode.contains('walk')) continue;
        final id = leg['route_id']?.toString();
        if (id != null && id.isNotEmpty && id != 'null') return id;
      }
    }
    return null;
  }

  String _vehicleLocationStatus(Map<String, dynamic> vehicle) {
    final apiStatus = vehicle['location_status']?.toString();
    if (apiStatus == 'stale' || apiStatus == 'unavailable') return apiStatus!;
    final raw = vehicle['last_updated']?.toString();
    if (raw == null || raw.isEmpty) return 'unavailable';
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return 'unavailable';
    final age = DateTime.now().toUtc().difference(parsed.toUtc());
    if (age > const Duration(minutes: 5)) return 'unavailable';
    if (age > const Duration(seconds: 60)) return 'stale';
    return 'active';
  }

  String _trackingSubtitle() {
    if (_vehiclesById.isEmpty) {
      return _trackingMessage ?? 'Showing backend geometry and stops';
    }
    final firstVehicle = _vehiclesById.values.first;
    final vehicleId = firstVehicle['vehicle_id']?.toString() ?? 'vehicle';
    final speed = firstVehicle['speed'];
    final updated = firstVehicle['last_updated']?.toString();
    final speedText = speed is num ? ' at ${speed.toStringAsFixed(0)} km/h' : '';
    final timeText = updated == null ? '' : ' - updated ${_relativeTime(updated)}';
    return 'Tracking $vehicleId$speedText$timeText';
  }

  Future<void> _startNavigation() async {
    final routeId = _routeId(_effectiveRoute);
    if (routeId == null) {
      setState(() {
        _trackingMessage = 'Select a route to start navigation.';
      });
      return;
    }

    final connected = await widget.connect(
      'Start navigation',
      () => widget.services.startTrip(routeId),
    );
    if (!mounted || !connected) return;

    setState(() {
      _navigationStarted = true;
    });
    await _pollVehicles();
  }

  String _relativeTime(String raw) {
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return '--';
    final age = DateTime.now().toUtc().difference(parsed.toUtc());
    if (age.inSeconds < 60) return '${age.inSeconds}s ago';
    if (age.inMinutes < 60) return '${age.inMinutes}m ago';
    return '${age.inHours}h ago';
  }

  @override
  Widget build(BuildContext context) {
    final route = _effectiveRoute;
    final routeTitle = _routeTitle(route);
    final routeSubtitle = _routeSubtitle(route);
    final routeMinutes = _routeMinutes(route);
    final routeFare = _routeFare(route);
    final routeStops = _routeStops(route);
    final primaryMode = _primaryMode(route);
    final primaryColor = colorForMode(primaryMode);

    return Column(
      children: [
        Container(
          color: green,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
          child: SafeArea(
            bottom: false,
            child: Column(
              children: [
                HeaderRow(
                    title: 'Route Details',
                    onBack: () => widget.onGo(AppScreen.planTrip)),
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 52,
                            height: 52,
                            decoration: BoxDecoration(
                              color: primaryColor,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Icon(iconForMode(primaryMode),
                                color: Colors.white),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(routeTitle,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w900,
                                        fontSize: 18)),
                                const SizedBox(height: 4),
                                Text(routeSubtitle,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(color: muted)),
                              ],
                            ),
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(routeMinutes,
                                  style: TextStyle(
                                      color: primaryColor, fontSize: 24)),
                              const Text('TRIP',
                                  style: TextStyle(color: muted, fontSize: 10)),
                            ],
                          ),
                        ],
                      ),
                      const Divider(height: 24),
                      Row(
                        children: [
                          const Icon(Icons.timeline, size: 16, color: muted),
                          const SizedBox(width: 6),
                          Text('${routeStops.length} stops'),
                          const SizedBox(width: 18),
                          const Icon(Icons.swap_calls, size: 18, color: muted),
                          const SizedBox(width: 4),
                          Text('${route?['transfer_count'] ?? 0} transfers'),
                          const Spacer(),
                          Text(routeFare,
                              style: TextStyle(color: primaryColor)),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(bottom: BorderSide(color: softLine)),
          ),
          child: Row(
            children: [
              const _MapPin(
                  icon: Icons.navigation, bg: Color(0xFFDDF8EF), color: green),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Route Map',
                        style: TextStyle(fontWeight: FontWeight.w700)),
                    Text(
                        route == null
                            ? 'Select a backend route to view its map'
                            : _trackingSubtitle(),
                        style: const TextStyle(fontSize: 12, color: muted)),
                  ],
                ),
              ),
              FilledButton(
                onPressed: () => _pollVehicles(),
                style: FilledButton.styleFrom(backgroundColor: green),
                child: const Text('Track'),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(18, 22, 18, 18),
            children: [
              SizedBox(
                height: 220,
                child: RouteMapPreview(
                  route: route,
                  liveVehicles: _vehiclesById.values.toList(),
                ),
              ),
              const SizedBox(height: 12),
              _TrackingStatusBar(
                loading: _trackingLoading,
                message: _trackingMessage,
                vehicles: _vehiclesById.values.toList(),
              ),
              const SizedBox(height: 20),
              SectionTitle(
                  title: 'Route Stops', trailing: '${routeStops.length} stops'),
              const SizedBox(height: 14),
              RouteStopsTimeline(stops: routeStops),
              const SizedBox(height: 18),
              DriverCard(services: widget.services, connect: widget.connect),
              const SizedBox(height: 20),
              Row(
                children: [
                  Expanded(
                      child: OutlinedButton(
                          onPressed: () =>
                              widget.connect('Share trip', widget.services.shareTrip),
                          child: const Text('Share Trip'))),
                  const SizedBox(width: 12),
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () async {
                        await widget.connect(
                            'Cancel trip', widget.services.cancelTrip);
                        widget.onGo(AppScreen.home);
                      },
                      style: OutlinedButton.styleFrom(
                          foregroundColor: rose,
                          side: const BorderSide(color: rose)),
                      child: const Text('Cancel Trip'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 16),
          decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(top: BorderSide(color: softLine))),
          child: SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: _startNavigation,
              style: FilledButton.styleFrom(
                  backgroundColor: green, padding: const EdgeInsets.all(16)),
              child: Text(
                  _navigationStarted ? 'Navigation Active' : 'Start Navigation',
                  style: const TextStyle(fontWeight: FontWeight.w800)),
            ),
          ),
        ),
      ],
    );
  }

  String _routeTitle(Map<String, dynamic>? route) {
    final labels = _routeLabels(route);
    if (labels.isEmpty) return 'Selected Route';
    return labels.take(2).join(' + ');
  }

  String _routeSubtitle(Map<String, dynamic>? route) {
    final stops = _routeStops(route);
    if (stops.length >= 2) {
      return '${stops.first.name} - ${stops.last.name}';
    }
    return route?['label']?.toString() ?? 'Backend route details';
  }

  String _routeMinutes(Map<String, dynamic>? route) {
    final seconds = route?['total_travel_time'];
    if (seconds is num) return '${(seconds / 60).round()} min';
    return '-- min';
  }

  String _routeFare(Map<String, dynamic>? route) {
    final fare = route?['total_fare'];
    if (fare is num) {
      final value =
          fare % 1 == 0 ? fare.toInt().toString() : fare.toStringAsFixed(1);
      return '$value EGP';
    }
    return '${fare ?? '--'} EGP';
  }

  List<String> _routeLabels(Map<String, dynamic>? route) {
    final legs = route?['legs'];
    if (legs is! List) return const [];
    return legs
        .whereType<Map<String, dynamic>>()
        .map((leg) => leg['route_label'] ?? leg['route_id'] ?? leg['mode'])
        .whereType<Object>()
        .map((label) => label.toString())
        .where((label) => label.isNotEmpty && label != 'null')
        .toSet()
        .toList();
  }

  String _primaryMode(Map<String, dynamic>? route) {
    final legs = route?['legs'];
    if (legs is! List) return 'bus';
    for (final leg in legs.whereType<Map<String, dynamic>>()) {
      final mode = (leg['mode'] ?? '').toString();
      if (!mode.toLowerCase().contains('walk')) return mode;
    }
    return 'walk';
  }

  List<RouteStopData> _routeStops(Map<String, dynamic>? route) {
    final legs = route?['legs'];
    if (legs is! List) return _fallbackStops();

    final stops = <RouteStopData>[];
    for (final leg in legs.whereType<Map<String, dynamic>>()) {
      final fromStop = _stopName(leg['from_stop']) ?? leg['from_stop_id'];
      final toStop = _stopName(leg['to_stop']) ?? leg['to_stop_id'];
      final departure = leg['departure_time']?.toString();
      final arrival = leg['arrival_time']?.toString();
      final mode = (leg['mode'] ?? '').toString();

      if (fromStop != null && stops.isEmpty) {
        stops.add(RouteStopData(
          name: fromStop.toString(),
          detail: departure == null ? 'Origin' : 'Departure: $departure',
          color: green,
          mode: mode,
          tag: 'Start',
        ));
      }

      if (toStop != null) {
        stops.add(RouteStopData(
          name: toStop.toString(),
          detail: arrival == null ? 'Stop' : 'Arrival: $arrival',
          color: leg == legs.last ? rose : muted,
          mode: mode,
          tag: leg == legs.last ? 'End' : '',
        ));
      }
    }

    return stops.isEmpty ? _fallbackStops() : stops;
  }

  Object? _stopName(Object? stop) {
    if (stop is Map) {
      return stop['name'] ?? stop['stop_name'] ?? stop['stop_id'];
    }
    return null;
  }

  List<RouteStopData> _fallbackStops() {
    return const [
      RouteStopData(
          name: 'Heliopolis Square',
          detail: 'Next stop - Arrival: 3:45 PM',
          color: green,
          tag: 'Next'),
      RouteStopData(name: 'Salah Salem', detail: 'Arrival: 3:52 PM'),
      RouteStopData(name: 'Abbas El Akkad', detail: 'Arrival: 3:58 PM'),
      RouteStopData(name: 'Tahrir Square', detail: 'Arrival: 4:05 PM'),
      RouteStopData(name: 'Garden City', detail: 'Arrival: 4:12 PM'),
      RouteStopData(
          name: 'Maadi Corniche',
          detail: 'Your destination - Arrival: 4:20 PM',
          color: rose,
          tag: 'End'),
    ];
  }
}

class WalletScreen extends StatelessWidget {
  const WalletScreen({
    super.key,
    required this.services,
    required this.connect,
    required this.onGo,
    required this.showTicket,
    required this.onToggleTicket,
  });

  final AppServices services;
  final BackendConnector connect;
  final ValueChanged<AppScreen> onGo;
  final bool showTicket;
  final Future<void> Function() onToggleTicket;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        BackendLoader(
          action: 'Wallet',
          connect: connect,
          request: services.loadWallet,
        ),
        Container(
          color: green,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 90),
          child: SafeArea(
            bottom: false,
            child: HeaderRow(
                title: 'My Wallet', onBack: () => onGo(AppScreen.home)),
          ),
        ),
        Expanded(
          child: Transform.translate(
            offset: const Offset(0, -56),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
              children: [
                WalletBalance(
                  services: services,
                  connect: connect,
                  onToggleTicket: onToggleTicket,
                ),
                const SizedBox(height: 16),
                Row(
                  children: const [
                    Expanded(
                        child: StatCard(
                            icon: Icons.trending_up,
                            title: 'This Month',
                            value: '45 EGP',
                            note: '3 trips')),
                    SizedBox(width: 12),
                    Expanded(
                        child: StatCard(
                            icon: Icons.schedule,
                            title: 'Avg. Trip',
                            value: '15 EGP',
                            note: 'per ride')),
                  ],
                ),
                const SizedBox(height: 22),
                if (showTicket)
                  DigitalTicket(
                      services: services,
                      connect: connect,
                      onClose: onToggleTicket)
                else
                  WalletTransactions(services: services, connect: connect),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({
    super.key,
    required this.services,
    required this.connect,
    required this.onGo,
  });

  final AppServices services;
  final BackendConnector connect;
  final ValueChanged<AppScreen> onGo;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        BackendLoader(
          action: 'Notifications',
          connect: connect,
          request: services.loadNotifications,
        ),
        Container(
          color: green,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
          child: SafeArea(
            bottom: false,
            child: Row(
              children: [
                IconButton(
                    onPressed: () => onGo(AppScreen.home),
                    icon: const Icon(Icons.arrow_back, color: Colors.white)),
                const Text('Notifications',
                    style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w900,
                        fontSize: 18)),
                const Spacer(),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                  decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(999)),
                  child: const Text('2 new',
                      style:
                          TextStyle(color: green, fontWeight: FontWeight.w700)),
                ),
              ],
            ),
          ),
        ),
        Container(
          color: Colors.white,
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 12),
          child: Row(
            children: const [
              FilterChipLike(label: 'All', active: true),
              FilterChipLike(label: 'Alerts'),
              FilterChipLike(label: 'Updates'),
              FilterChipLike(label: 'Trips'),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            padding: EdgeInsets.zero,
            children: const [
              NoticeTile(
                  icon: Icons.error_outline,
                  bg: Color(0xFFFFF7DC),
                  color: Color(0xFFF59E0B),
                  title: 'Route Delay',
                  body:
                      'Bus B101 is delayed by 5 minutes due to heavy traffic on Salah Salem',
                  time: '5 min ago',
                  unread: true),
              NoticeTile(
                  icon: Icons.info_outline,
                  bg: Color(0xFFEFF6FF),
                  color: Color(0xFF2563EB),
                  title: 'New Route Available',
                  body:
                      'Direct route from Heliopolis to New Cairo now available',
                  time: '1 hour ago',
                  unread: true),
              NoticeTile(
                  icon: Icons.check_circle_outline,
                  bg: paleGreen,
                  color: green,
                  title: 'Payment Successful',
                  body: 'Your wallet has been topped up with 100 EGP',
                  time: '2 hours ago'),
              NoticeTile(
                  icon: Icons.error_outline,
                  bg: Color(0xFFFFEBEE),
                  color: rose,
                  title: 'Service Interruption',
                  body:
                      'Route M45 temporarily unavailable due to road maintenance',
                  time: 'Yesterday'),
              NoticeTile(
                  icon: Icons.schedule,
                  bg: Color(0xFFEFF6FF),
                  color: Color(0xFF2563EB),
                  title: 'Schedule Update',
                  body:
                      'Weekend schedules updated for all routes in Maadi area',
                  time: '2 days ago'),
              NoticeTile(
                  icon: Icons.check_circle_outline,
                  bg: paleGreen,
                  color: green,
                  title: 'Trip Completed',
                  body: "You've earned 10 loyalty points for your last trip",
                  time: '3 days ago'),
            ],
          ),
        ),
      ],
    );
  }
}

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({
    super.key,
    required this.services,
    required this.connect,
    required this.onGo,
  });

  final AppServices services;
  final BackendConnector connect;
  final ValueChanged<AppScreen> onGo;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        BackendLoader(
          action: 'Profile',
          connect: connect,
          request: services.loadProfile,
        ),
        Container(
          color: green,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 90),
          child: SafeArea(
            bottom: false,
            child:
                HeaderRow(title: 'Profile', onBack: () => onGo(AppScreen.home)),
          ),
        ),
        Expanded(
          child: Transform.translate(
            offset: const Offset(0, -56),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(18, 0, 18, 26),
              children: [
                ProfileSummaryCard(),
                const SizedBox(height: 24),
                ProfileSection(
                  title: 'ACCOUNT',
                  children: [
                    ProfileSettingTile(
                        icon: Icons.person_outline,
                        title: 'Personal Information',
                        subtitle: 'Update your details'),
                    ProfileSettingTile(
                        icon: Icons.mail_outline,
                        title: 'Email Address',
                        subtitle: 'ahmed.hassan@email.com'),
                    ProfileSettingTile(
                        icon: Icons.phone_outlined,
                        title: 'Phone Number',
                        subtitle: '+20 123 456 7890'),
                  ],
                ),
                ProfileSection(
                  title: 'PREFERENCES',
                  children: [
                    ProfileSettingTile(
                        icon: Icons.credit_card,
                        title: 'Payment Methods',
                        subtitle: 'Manage your cards & wallet',
                        onTap: () async {
                          await connect('Wallet', services.loadWallet);
                          onGo(AppScreen.wallet);
                        }),
                    ProfileSettingTile(
                        icon: Icons.notifications_none,
                        title: 'Notifications',
                        subtitle: 'Push, email & SMS settings',
                        onTap: () async {
                          await connect(
                              'Notifications', services.loadNotifications);
                          onGo(AppScreen.notifications);
                        }),
                  ],
                ),
                ProfileSection(
                  title: 'SUPPORT',
                  children: [
                    ProfileSettingTile(
                        icon: Icons.help_outline,
                        title: 'Help & Support',
                        subtitle: 'FAQs and contact us',
                        blue: true),
                    ProfileSettingTile(
                        icon: Icons.shield_outlined,
                        title: 'Privacy & Security',
                        subtitle: 'Terms and conditions',
                        blue: true),
                    ProfileSettingTile(
                        icon: Icons.star_border,
                        title: 'Rate the App',
                        subtitle: 'Share your feedback',
                        blue: true),
                  ],
                ),
                const SizedBox(height: 10),
                SizedBox(
                  height: 54,
                  child: OutlinedButton.icon(
                    onPressed: () async {
                      await connect('Logout', services.logout);
                      onGo(AppScreen.auth);
                    },
                    style: OutlinedButton.styleFrom(
                      foregroundColor: rose,
                      side: const BorderSide(color: rose),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                      ),
                    ),
                    icon: const Icon(Icons.logout, size: 18),
                    label: const Text('Log Out',
                        style: TextStyle(fontWeight: FontWeight.w900)),
                  ),
                ),
                const SizedBox(height: 24),
                const Center(
                  child: Text('IZEE v1.0.0',
                      style: TextStyle(color: muted, fontSize: 11)),
                ),
                const SizedBox(height: 6),
                const Center(
                  child: Text('Made for Smart Cities in Egypt',
                      style: TextStyle(color: muted, fontSize: 11)),
                ),
                const SizedBox(height: 84),
              ],
            ),
          ),
        ),
        BottomNav(current: AppScreen.profile, onGo: onGo),
      ],
    );
  }
}

class BackendLoader extends StatefulWidget {
  const BackendLoader({
    super.key,
    required this.action,
    required this.connect,
    required this.request,
  });

  final String action;
  final BackendConnector connect;
  final Future<Map<String, dynamic>> Function() request;

  @override
  State<BackendLoader> createState() => _BackendLoaderState();
}

class _BackendLoaderState extends State<BackendLoader> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.connect(widget.action, widget.request, quiet: true);
    });
  }

  @override
  Widget build(BuildContext context) {
    return const SizedBox.shrink();
  }
}

class GreenHeader extends StatelessWidget {
  const GreenHeader(
      {super.key,
      required this.title,
      required this.child,
      required this.onBack,
      this.scrollable = false});

  final String title;
  final Widget child;
  final VoidCallback onBack;
  final bool scrollable;

  @override
  Widget build(BuildContext context) {
    final content = Column(
      children: [
        HeaderRow(title: title, onBack: onBack),
        const SizedBox(height: 14),
        if (scrollable) Expanded(child: child) else child,
      ],
    );

    return Container(
      color: green,
      padding: EdgeInsets.fromLTRB(16, 8, 16, scrollable ? 8 : 20),
      child: SafeArea(
        bottom: false,
        child: content,
      ),
    );
  }
}

class HeaderRow extends StatelessWidget {
  const HeaderRow({super.key, required this.title, required this.onBack});

  final String title;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        IconButton(
            onPressed: onBack,
            icon: const Icon(Icons.arrow_back, color: Colors.white)),
        Text(title,
            style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w900,
                fontSize: 18)),
        const Spacer(),
      ],
    );
  }
}

class BottomNav extends StatelessWidget {
  const BottomNav({super.key, required this.current, required this.onGo});

  final AppScreen current;
  final ValueChanged<AppScreen> onGo;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      color: Colors.white,
      child: SafeArea(
        top: false,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _NavItem(
                icon: Icons.location_on_outlined,
                label: 'Home',
                active: current == AppScreen.home,
                onTap: () => onGo(AppScreen.home)),
            _NavItem(
                icon: Icons.search,
                label: 'Search',
                active: current == AppScreen.planTrip,
                onTap: () => onGo(AppScreen.planTrip)),
            _NavItem(
                icon: Icons.account_balance_wallet_outlined,
                label: 'Wallet',
                active: current == AppScreen.wallet,
                onTap: () => onGo(AppScreen.wallet)),
            _NavItem(
                icon: Icons.person_outline,
                label: 'Profile',
                active: current == AppScreen.profile,
                onTap: () => onGo(AppScreen.profile)),
          ],
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem(
      {required this.icon,
      required this.label,
      required this.active,
      required this.onTap});

  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final color = active ? green : muted;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(
        width: 70,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(
                    color: color,
                    fontSize: 11,
                    fontWeight: active ? FontWeight.w800 : FontWeight.w500)),
          ],
        ),
      ),
    );
  }
}

class MapCanvas extends StatelessWidget {
  const MapCanvas({super.key});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: MapPainter(), child: Container());
  }
}

class RouteMapPreview extends StatelessWidget {
  const RouteMapPreview({
    super.key,
    required this.route,
    this.liveVehicles = const [],
  });

  final Map<String, dynamic>? route;
  final List<Map<String, dynamic>> liveVehicles;

  double? _asDouble(Object? value) {
    if (value is num) return value.toDouble();
    if (value == null) return null;
    return double.tryParse(value.toString());
  }

  @override
  Widget build(BuildContext context) {
    final segments = _geometrySegments(route);
    final points = segments.expand((segment) => segment.points).toList();

    debugPrint('PASSENGER_LIVE_VEHICLE_COUNT: ${liveVehicles.length}');
    debugPrint('PASSENGER_MARKERS_BEFORE: 0');
    final vehicleMarkers = <Marker>[];
    for (final vehicle in liveVehicles) {
      final lat = _asDouble(vehicle['lat']);
      final lon = _asDouble(vehicle['lng'] ?? vehicle['lon']);
      final heading = _asDouble(vehicle['heading']);
      final isStale = vehicle['location_status']?.toString() == 'stale' ||
          vehicle['stale'] == true;
      final vehicleId = vehicle['vehicle_id']?.toString() ?? 'unknown';
      debugPrint('PASSENGER_MARKER_UPDATE_VEHICLE_ID: $vehicleId');
      if (lat != null && lon != null) {
        vehicleMarkers.add(
          Marker(
            point: LatLng(lat, lon),
            width: 36,
            height: 36,
            child: Transform.rotate(
              angle: ((heading ?? 0) * math.pi) / 180,
              child: _MapPin(
                icon: Icons.directions_bus,
                bg: isStale ? const Color(0xFFFFF5E6) : paleGreen,
                color: isStale ? const Color(0xFFF5A623) : green,
              ),
            ),
          ),
        );
      }
    }
                const SizedBox(height: 6),
                Row(
                  children: [
                    const Icon(Icons.people_outline, size: 14, color: muted),
                    Text(' $seats',
                        style: const TextStyle(color: muted, fontSize: 11)),
                    const SizedBox(width: 10),
                    const Icon(Icons.star, size: 14, color: Color(0xFFFACC15)),
                    const Text(' 4.5',
                        style: TextStyle(color: muted, fontSize: 11)),
                  ],
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(time,
                  style: const TextStyle(
                      color: green, fontWeight: FontWeight.w800)),
              Text(distance,
                  style: const TextStyle(color: muted, fontSize: 10)),
            ],
          ),
        ],
      ),
    );
  }
}

class RouteCard extends StatelessWidget {
  const RouteCard({
    super.key,
    required this.chips,
    required this.tag,
    required this.minutes,
    required this.transfer,
    required this.walking,
    required this.arrival,
    required this.price,
    required this.badges,
    required this.steps,
    required this.depart,
    required this.onTap,
    this.selected = false,
  });

  final List<RouteChipData> chips;
  final String tag;
  final String minutes;
  final String transfer;
  final String walking;
  final String arrival;
  final String price;
  final List<String> badges;
  final List<RouteLegData> steps;
  final String depart;
  final VoidCallback onTap;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return CardShell(
      onTap: onTap,
      borderColor: selected ? green : softLine,
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final chip in chips)
                      _RoutePill(chip.label, mode: chip.mode),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 150),
                child: Wrap(
                  alignment: WrapAlignment.end,
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final badge in badges) _SmallTag(label: badge),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: Wrap(
                  spacing: 14,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    _RouteMetric(icon: Icons.schedule, label: minutes),
                    _RouteMetric(icon: Icons.trending_up, label: transfer),
                    _RouteMetric(icon: Icons.directions_walk, label: walking),
                    _RouteMetric(icon: Icons.flag_outlined, label: arrival),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  price,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.end,
                  style: const TextStyle(
                      color: green, fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
          const Divider(height: 24),
          for (final step in steps.take(6))
            Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: Row(
                children: [
                  _MapPin(
                      icon: iconForMode(step.mode),
                      bg: colorForMode(step.mode).withValues(alpha: .12),
                      color: colorForMode(step.mode),
                      size: 24,
                      iconSize: 13),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(step.title,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                color: ink,
                                fontSize: 13,
                                fontWeight: FontWeight.w800)),
                        const SizedBox(height: 3),
                        Text(step.detail,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(color: muted, fontSize: 12)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          Text(depart, style: const TextStyle(color: muted, fontSize: 12)),
        ],
      ),
    );
  }
}

class _RouteMetric extends StatelessWidget {
  const _RouteMetric({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: muted),
        const SizedBox(width: 4),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 105),
          child: Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: ink),
          ),
        ),
      ],
    );
  }
}

class _TrackingStatusBar extends StatelessWidget {
  const _TrackingStatusBar({
    required this.loading,
    required this.message,
    required this.vehicles,
  });

  final bool loading;
  final String? message;
  final List<Map<String, dynamic>> vehicles;

  @override
  Widget build(BuildContext context) {
    final hasVehicle = vehicles.isNotEmpty;
    final vehicle = hasVehicle ? vehicles.first : null;
    final vehicleId = vehicle?['vehicle_id']?.toString();
    final speed = vehicle?['speed'];
    final lastUpdated = vehicle?['last_updated']?.toString();

    final text = message ??
        (hasVehicle
            ? [
                if (vehicleId != null && vehicleId.isNotEmpty)
                  'Vehicle $vehicleId',
                if (speed is num) '${speed.toStringAsFixed(0)} km/h',
                if (lastUpdated != null) 'Updated ${_relative(lastUpdated)}',
                'ETA pending',
              ].join(' - ')
            : 'No active vehicle currently available for this route.');

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: hasVehicle ? const Color(0xFFDDF8EF) : const Color(0xFFFFF5E6),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: hasVehicle ? green : const Color(0xFFF5A623)),
      ),
      child: Row(
        children: [
          if (loading)
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          else
            Icon(
              hasVehicle ? Icons.directions_bus : Icons.info_outline,
              color: hasVehicle ? green : const Color(0xFFF5A623),
              size: 18,
            ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }

  String _relative(String raw) {
    final parsed = DateTime.tryParse(raw);
    if (parsed == null) return '--';
    final age = DateTime.now().toUtc().difference(parsed.toUtc());
    if (age.inSeconds < 60) return '${age.inSeconds}s ago';
    if (age.inMinutes < 60) return '${age.inMinutes}m ago';
    return '${age.inHours}h ago';
  }
}

class RouteStopData {
  const RouteStopData({
    required this.name,
    required this.detail,
    this.mode = '',
    this.color = muted,
    this.tag = '',
  });

  final String name;
  final String detail;
  final String mode;
  final Color color;
  final String tag;
}

class RouteStopsTimeline extends StatelessWidget {
  const RouteStopsTimeline({super.key, required this.stops});

  final List<RouteStopData> stops;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Positioned(
            left: 17,
            top: 18,
            bottom: 28,
            child: Container(width: 2, color: softLine)),
        Column(
          children: [
            for (int i = 0; i < stops.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 18),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: 36,
                      height: 36,
                      decoration: BoxDecoration(
                        color: stops[i].color == rose
                            ? rose
                            : colorForMode(stops[i].mode),
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 5),
                      ),
                      child: Icon(
                        stops[i].tag == 'End'
                            ? Icons.location_on
                            : iconForMode(stops[i].mode),
                        color: Colors.white,
                        size: 16,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: CardShell(
                        padding: const EdgeInsets.all(16),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(stops[i].name,
                                      style: TextStyle(
                                          color: i == 0 ? green : ink,
                                          fontWeight: FontWeight.w900)),
                                  const SizedBox(height: 8),
                                  Text(stops[i].detail,
                                      style: const TextStyle(
                                          color: muted, fontSize: 12)),
                                ],
                              ),
                            ),
                            if (stops[i].tag.isNotEmpty)
                              _SmallTag(
                                  label: stops[i].tag,
                                  red: stops[i].tag == 'End'),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class WalletBalance extends StatelessWidget {
  const WalletBalance({
    super.key,
    required this.services,
    required this.connect,
    required this.onToggleTicket,
  });

  final AppServices services;
  final BackendConnector connect;
  final Future<void> Function() onToggleTicket;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: darkGreen,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Available Balance',
                        style: TextStyle(
                            color: Colors.white, fontWeight: FontWeight.w700)),
                    SizedBox(height: 6),
                    Text('250 EGP',
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 34,
                            fontWeight: FontWeight.w900)),
                  ],
                ),
              ),
              CircleAvatar(
                backgroundColor: Colors.white.withValues(alpha: .18),
                child: const Icon(Icons.credit_card, color: Colors.white),
              ),
            ],
          ),
          const SizedBox(height: 22),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: () =>
                      connect('Wallet top-up', services.topUpWallet),
                  style: FilledButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: green,
                      padding: const EdgeInsets.all(14)),
                  icon: const Icon(Icons.add),
                  label: const Text('Top Up',
                      style: TextStyle(fontWeight: FontWeight.w900)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.icon(
                  onPressed: () => onToggleTicket(),
                  style: FilledButton.styleFrom(
                      backgroundColor: Colors.white.withValues(alpha: .18),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.all(14)),
                  icon: const Icon(Icons.qr_code_2),
                  label: const Text('Scan',
                      style: TextStyle(fontWeight: FontWeight.w900)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class WalletTransactions extends StatelessWidget {
  const WalletTransactions({
    super.key,
    required this.services,
    required this.connect,
  });

  final AppServices services;
  final BackendConnector connect;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionTitle(
            title: 'Recent Transactions',
            trailing: 'View All',
            trailingColor: green),
        const SizedBox(height: 14),
        const TxTile(
            icon: Icons.credit_card,
            title: 'B101 - Heliopolis to Maadi',
            time: 'Today, 3:45 PM',
            amount: '- 15 EGP'),
        const TxTile(
            icon: Icons.add,
            title: 'Wallet Top-up',
            time: 'Today, 2:30 PM',
            amount: '+ 100 EGP',
            positive: true),
        const TxTile(
            icon: Icons.credit_card,
            title: 'M45 - Nasr City to Downtown',
            time: 'Yesterday, 5:20 PM',
            amount: '- 12 EGP'),
        const TxTile(
            icon: Icons.credit_card,
            title: 'B89 - 6th October to Tahrir',
            time: 'Dec 12, 10:15 AM',
            amount: '- 18 EGP'),
        const SizedBox(height: 18),
        const Text('Payment Methods',
            style: TextStyle(fontWeight: FontWeight.w900, fontSize: 18)),
        const SizedBox(height: 14),
        CardShell(
          borderColor: green,
          child: Row(
            children: [
              const _MapPin(
                  icon: Icons.credit_card, bg: paleGreen, color: green),
              const SizedBox(width: 12),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('IZEE Wallet',
                        style: TextStyle(fontWeight: FontWeight.w800)),
                    Text('Primary payment method',
                        style: TextStyle(color: muted, fontSize: 12)),
                  ],
                ),
              ),
              _SmallTag(label: 'Active', filled: true),
            ],
          ),
        ),
        const SizedBox(height: 10),
        SizedBox(
          height: 54,
          child: OutlinedButton.icon(
            onPressed: () =>
                connect('Payment method', services.addPaymentMethod),
            style: OutlinedButton.styleFrom(
              foregroundColor: muted,
              side: const BorderSide(color: softLine),
              backgroundColor: const Color(0xFFF7F7F9),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            icon: const Icon(Icons.add),
            label: const Text(
              'Add Payment Method',
              style: TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
        ),
      ],
    );
  }
}

class DigitalTicket extends StatelessWidget {
  const DigitalTicket({
    super.key,
    required this.services,
    required this.connect,
    required this.onClose,
  });

  final AppServices services;
  final BackendConnector connect;
  final Future<void> Function() onClose;

  @override
  Widget build(BuildContext context) {
    return CardShell(
      borderColor: green,
      padding: const EdgeInsets.all(22),
      child: Column(
        children: [
          Row(
            children: [
              const Text('Digital Ticket',
                  style: TextStyle(fontWeight: FontWeight.w900, fontSize: 20)),
              const Spacer(),
              TextButton(
                  onPressed: () => onClose(),
                  child: const Text('Close', style: TextStyle(color: muted))),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(26),
            decoration: BoxDecoration(
                border: Border.all(color: softLine),
                borderRadius: BorderRadius.circular(14)),
            child: Container(
              height: 264,
              decoration: BoxDecoration(
                  color: paleGreen, borderRadius: BorderRadius.circular(12)),
              child:
                  CustomPaint(painter: TicketDotsPainter(), child: Container()),
            ),
          ),
          const SizedBox(height: 18),
          const Text('Ticket ID', style: TextStyle(color: muted)),
          const SizedBox(height: 8),
          const Text('IZEE-2024-12-1234', style: TextStyle(fontSize: 16)),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: () =>
                      connect('NFC ticket', services.createTicketScan),
                  style: FilledButton.styleFrom(
                      backgroundColor: paleGreen,
                      foregroundColor: green,
                      padding: const EdgeInsets.all(14)),
                  icon: const Icon(Icons.phone_iphone, size: 18),
                  label: const Text('NFC Ready',
                      style: TextStyle(fontWeight: FontWeight.w900)),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  onPressed: () => connect('Save ticket', services.saveTicket),
                  style: FilledButton.styleFrom(
                      backgroundColor: green,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.all(14)),
                  icon: const Icon(Icons.download, size: 18),
                  label: const Text('Save',
                      style: TextStyle(fontWeight: FontWeight.w900)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class TicketDotsPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.black;
    final dots = [
      [4, 2],
      [5, 2],
      [7, 2],
      [8, 2],
      [10, 2],
      [4, 3],
      [6, 3],
      [8, 3],
      [11, 3],
      [9, 4],
      [11, 4],
      [12, 4],
      [8, 5],
      [9, 5],
      [11, 5],
      [5, 6],
      [6, 6],
      [8, 6],
      [10, 6],
      [12, 6],
      [5, 7],
      [7, 7],
      [9, 7],
      [11, 7],
      [4, 8],
      [5, 8],
      [6, 8],
      [10, 8],
    ];
    final cell = size.shortestSide / 16;
    final origin =
        Offset(size.width / 2 - cell * 8, size.height / 2 - cell * 5);
    for (final dot in dots) {
      canvas.drawCircle(
          origin + Offset(dot[0] * cell, dot[1] * cell), cell * .38, paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class CardShell extends StatelessWidget {
  const CardShell({
    super.key,
    required this.child,
    this.onTap,
    this.margin,
    this.padding = const EdgeInsets.all(12),
    this.borderColor = softLine,
    this.color = Colors.white,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry? margin;
  final EdgeInsetsGeometry padding;
  final Color borderColor;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: margin,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
            color: borderColor, width: borderColor == green ? 1.5 : 1),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withValues(alpha: .06),
              blurRadius: 5,
              offset: const Offset(0, 2)),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(padding: padding, child: child),
        ),
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(
      {super.key,
      required this.title,
      required this.trailing,
      this.trailingColor = muted});

  final String title;
  final String trailing;
  final Color trailingColor;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(title,
            style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 18)),
        const Spacer(),
        Text(trailing,
            style: TextStyle(
                color: trailingColor,
                fontSize: 13,
                fontWeight: trailingColor == green
                    ? FontWeight.w800
                    : FontWeight.w500)),
      ],
    );
  }
}

class LocationField extends StatelessWidget {
  const LocationField({
    super.key,
    required this.icon,
    required this.controller,
    this.focusNode,
    this.red = false,
    this.trailing,
    this.onSubmitted,
  });

  final IconData icon;
  final TextEditingController controller;
  final FocusNode? focusNode;
  final bool red;
  final Widget? trailing;
  final ValueChanged<String>? onSubmitted;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
          color: Colors.white, borderRadius: BorderRadius.circular(12)),
      child: Row(
        children: [
          _MapPin(
              icon: icon,
              bg: red ? const Color(0xFFFFEEF2) : paleGreen,
              color: red ? rose : green),
          const SizedBox(width: 14),
          Expanded(
            child: TextField(
              controller: controller,
              focusNode: focusNode,
              onSubmitted: onSubmitted,
              decoration: const InputDecoration(
                border: InputBorder.none,
                isCollapsed: true,
              ),
              style: const TextStyle(fontSize: 16),
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: 8),
            trailing!,
          ],
        ],
      ),
    );
  }
}

class PlaceSuggestions extends StatelessWidget {
  const PlaceSuggestions({
    super.key,
    required this.places,
    required this.loading,
    required this.noResults,
    required this.onSelect,
    this.scrollable = false,
    this.red = false,
  });

  final List<Map<String, dynamic>> places;
  final bool loading;
  final bool noResults;
  final ValueChanged<Map<String, dynamic>> onSelect;
  final bool scrollable;
  final bool red;

  @override
  Widget build(BuildContext context) {
    if (!loading && places.isEmpty && !noResults) {
      return const SizedBox.shrink();
    }

    return Container(
      margin: const EdgeInsets.only(top: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.white.withValues(alpha: .5)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x22000000),
            blurRadius: 14,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: loading
          ? const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  SizedBox(width: 12),
                  Text('Searching places...',
                      style: TextStyle(color: muted, fontSize: 13)),
                ],
              ),
            )
          : noResults
              ? const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  child: Row(
                    children: [
                      Icon(Icons.search_off, color: muted, size: 18),
                      SizedBox(width: 10),
                      Text('No results found',
                          style: TextStyle(color: muted, fontSize: 13)),
                    ],
                  ),
                )
              : ListView.separated(
                  padding: EdgeInsets.zero,
                  shrinkWrap: !scrollable,
                  physics: scrollable
                      ? const ClampingScrollPhysics()
                      : const NeverScrollableScrollPhysics(),
                  itemCount: places.length,
                  separatorBuilder: (_, __) =>
                      const Divider(height: 1, color: softLine),
                  itemBuilder: (context, index) => _PlaceSuggestionTile(
                    place: places[index],
                    red: red,
                    showDivider: false,
                    onTap: () => onSelect(places[index]),
                  ),
                ),
    );
  }
}

class _PlaceSuggestionTile extends StatelessWidget {
  const _PlaceSuggestionTile({
    required this.place,
    required this.onTap,
    required this.red,
    required this.showDivider,
  });

  final Map<String, dynamic> place;
  final VoidCallback onTap;
  final bool red;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    final title =
        (place['name'] ?? place['display_name'] ?? place['label'] ?? 'Place')
            .toString();
    final subtitle = _suggestionSubtitle(place);

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          border: showDivider
              ? const Border(bottom: BorderSide(color: softLine))
              : null,
        ),
        child: Row(
          children: [
            _MapPin(
              icon: Icons.place_outlined,
              bg: red ? const Color(0xFFFFEEF2) : paleGreen,
              color: red ? rose : green,
              size: 30,
              iconSize: 16,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title.split(',').first.trim(),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        color: ink, fontWeight: FontWeight.w800),
                  ),
                  if (subtitle.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(color: muted, fontSize: 11),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

String _suggestionSubtitle(Map<String, dynamic> place) {
  final explicitSubtitle = place['subtitle']?.toString().trim();
  if (explicitSubtitle != null && explicitSubtitle.isNotEmpty) {
    return explicitSubtitle;
  }

  final type = (place['result_type'] ?? place['type'] ?? '').toString();
  final mode = (place['mode'] ?? '').toString().toLowerCase();

  if (type == 'transit_stop') {
    if (mode.contains('brt')) return '\u0645\u062d\u0637\u0629 BRT';
    if (mode.contains('lrt')) return '\u0645\u062d\u0637\u0629 LRT';
    if (mode.contains('metro')) {
      return '\u0645\u062d\u0637\u0629 \u0645\u062a\u0631\u0648';
    }
    if (mode.contains('microbus')) {
      return '\u0645\u062d\u0637\u0629 \u0645\u064a\u0643\u0631\u0648\u0628\u0627\u0635';
    }
    if (mode.contains('minibus')) {
      return '\u0645\u062d\u0637\u0629 \u0645\u064a\u0646\u064a \u0628\u0627\u0635';
    }
    return '\u0645\u062d\u0637\u0629';
  }

  if (type == 'district') return '\u0645\u0646\u0637\u0642\u0629';
  if (type == 'landmark') {
    return '\u0645\u0643\u0627\u0646 \u0645\u0645\u064a\u0632';
  }
  if (type == 'osm_place' || place['source'] == 'openstreetmap') {
    return '\u0645\u0643\u0627\u0646';
  }

  return [
    if (place['lat'] != null) place['lat'].toString(),
    if (place['lon'] != null) place['lon'].toString(),
  ].join(', ');
}

class DriverCard extends StatelessWidget {
  const DriverCard({
    super.key,
    required this.services,
    required this.connect,
  });

  final AppServices services;
  final BackendConnector connect;

  @override
  Widget build(BuildContext context) {
    return CardShell(
      color: const Color(0xFFF3FCF8),
      child: Row(
        children: [
          const CircleAvatar(
              backgroundColor: Color(0xFFDDF8EF),
              child: Text('MH', style: TextStyle(color: green))),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Mohamed Hassan',
                    style: TextStyle(fontWeight: FontWeight.w800)),
                SizedBox(height: 4),
                Row(
                  children: [
                    Icon(Icons.star, color: Color(0xFFFACC15), size: 15),
                    Icon(Icons.star, color: Color(0xFFFACC15), size: 15),
                    Icon(Icons.star, color: Color(0xFFFACC15), size: 15),
                    Icon(Icons.star, color: Color(0xFFFACC15), size: 15),
                    Icon(Icons.star, color: Color(0xFFFACC15), size: 15),
                    Text(' 5.0 (243 trips)',
                        style: TextStyle(color: muted, fontSize: 12)),
                  ],
                ),
              ],
            ),
          ),
          FilledButton(
              onPressed: () => connect('Driver call', services.callDriver),
              style: FilledButton.styleFrom(backgroundColor: green),
              child: const Text('Call')),
        ],
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  const _ModeChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 44,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: .2),
          borderRadius: BorderRadius.circular(9)),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: Colors.white, size: 16),
          const SizedBox(width: 6),
          Flexible(
            child: FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(label,
                  maxLines: 1,
                  style: const TextStyle(
                      color: Colors.white, fontWeight: FontWeight.w800)),
            ),
          ),
        ],
      ),
    );
  }
}

class _RoutePill extends StatelessWidget {
  const _RoutePill(this.text, {required this.mode});

  final String text;
  final String mode;

  @override
  Widget build(BuildContext context) {
    final color = colorForMode(mode);
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 122),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(iconForMode(mode), color: Colors.white, size: 15),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                text,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                    color: Colors.white, fontWeight: FontWeight.w900),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SmallTag extends StatelessWidget {
  const _SmallTag({required this.label, this.red = false, this.filled = false});

  final String label;
  final bool red;
  final bool filled;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
      decoration: BoxDecoration(
        color: filled
            ? green
            : red
                ? const Color(0xFFFFEBF0)
                : paleGreen,
        borderRadius: BorderRadius.circular(6),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 92),
        child: Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.center,
          style: TextStyle(
              color: filled
                  ? Colors.white
                  : red
                      ? rose
                      : green,
              fontSize: 12,
              fontWeight: FontWeight.w800),
        ),
      ),
    );
  }
}

class _MapPin extends StatelessWidget {
  const _MapPin(
      {required this.icon,
      required this.bg,
      required this.color,
      this.size = 36,
      this.iconSize = 20});

  final IconData icon;
  final Color bg;
  final Color color;
  final double size;
  final double iconSize;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
      child: Icon(icon, color: color, size: iconSize),
    );
  }
}

class _CircleButton extends StatelessWidget {
  const _CircleButton(
      {required this.icon, required this.color, required this.onTap});

  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      shape: const CircleBorder(),
      elevation: 7,
      child: IconButton(
          onPressed: onTap, icon: Icon(icon, color: color, size: 20)),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(3),
      decoration: const BoxDecoration(color: rose, shape: BoxShape.circle),
      child: Text(text,
          style: const TextStyle(
              color: Colors.white, fontSize: 9, fontWeight: FontWeight.w900)),
    );
  }
}

class StatCard extends StatelessWidget {
  const StatCard(
      {super.key,
      required this.icon,
      required this.title,
      required this.value,
      required this.note});

  final IconData icon;
  final String title;
  final String value;
  final String note;

  @override
  Widget build(BuildContext context) {
    return CardShell(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _MapPin(
                  icon: icon,
                  bg: paleGreen,
                  color: green,
                  size: 34,
                  iconSize: 18),
              const SizedBox(width: 8),
              Expanded(
                  child: Text(title, style: const TextStyle(color: muted))),
            ],
          ),
          const SizedBox(height: 18),
          Text(value,
              style:
                  const TextStyle(fontSize: 22, fontWeight: FontWeight.w500)),
          const SizedBox(height: 6),
          Text(note, style: const TextStyle(color: muted, fontSize: 12)),
        ],
      ),
    );
  }
}

class TxTile extends StatelessWidget {
  const TxTile(
      {super.key,
      required this.icon,
      required this.title,
      required this.time,
      required this.amount,
      this.positive = false});

  final IconData icon;
  final String title;
  final String time;
  final String amount;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    return CardShell(
      margin: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          _MapPin(icon: icon, bg: paleGreen, color: green),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Text(time, style: const TextStyle(color: muted, fontSize: 12)),
              ],
            ),
          ),
          Text(amount,
              style: TextStyle(
                  color: positive ? green : ink, fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class FilterChipLike extends StatelessWidget {
  const FilterChipLike({super.key, required this.label, this.active = false});

  final String label;
  final bool active;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.symmetric(horizontal: 17, vertical: 10),
      decoration: BoxDecoration(
        color: active ? green : const Color(0xFFF4F4F5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(label,
          style: TextStyle(
              color: active ? Colors.white : muted,
              fontWeight: FontWeight.w800)),
    );
  }
}

class NoticeTile extends StatelessWidget {
  const NoticeTile({
    super.key,
    required this.icon,
    required this.bg,
    required this.color,
    required this.title,
    required this.body,
    required this.time,
    this.unread = false,
  });

  final IconData icon;
  final Color bg;
  final Color color;
  final String title;
  final String body;
  final String time;
  final bool unread;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _MapPin(icon: icon, bg: bg, color: color),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                        child: Text(title,
                            style: const TextStyle(
                                fontWeight: FontWeight.w900, fontSize: 16))),
                    if (unread) const _UnreadDot(),
                  ],
                ),
                const SizedBox(height: 6),
                Text(body, style: const TextStyle(color: muted, height: 1.45)),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Text(time,
                        style: const TextStyle(color: muted, fontSize: 12)),
                    if (unread)
                      const Text('   Mark as read',
                          style: TextStyle(
                              color: green,
                              fontSize: 12,
                              fontWeight: FontWeight.w800)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _UnreadDot extends StatelessWidget {
  const _UnreadDot();

  @override
  Widget build(BuildContext context) {
    return Container(
        width: 8,
        height: 8,
        decoration: const BoxDecoration(color: green, shape: BoxShape.circle));
  }
}

class RecentSearch extends StatelessWidget {
  const RecentSearch({super.key, required this.text, this.onTap});

  final String text;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: const Color(0xFFF4F4F5),
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            child: Row(
              children: [
                const Icon(Icons.schedule, color: muted, size: 18),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    text,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                if (onTap != null) ...[
                  const SizedBox(width: 8),
                  const Icon(Icons.north_east, color: muted, size: 16),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AuthTab extends StatelessWidget {
  const _AuthTab({
    required this.label,
    required this.active,
    required this.onTap,
  });

  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: active ? Colors.white : Colors.transparent,
      borderRadius: BorderRadius.circular(7),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(7),
        child: SizedBox(
          height: 42,
          child: Center(
            child: Text(
              label,
              style: TextStyle(
                color: active ? ink : muted,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class FormFieldBox extends StatelessWidget {
  const FormFieldBox({
    super.key,
    required this.controller,
    required this.label,
    required this.hint,
    required this.icon,
    this.obscure = false,
  });

  final TextEditingController controller;
  final String label;
  final String hint;
  final IconData icon;
  final bool obscure;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          TextField(
            controller: controller,
            obscureText: obscure,
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: const TextStyle(color: muted),
              prefixIcon: Icon(icon, color: muted, size: 20),
              filled: true,
              fillColor: const Color(0xFFF3F3F5),
              contentPadding: const EdgeInsets.symmetric(vertical: 16),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(9),
                borderSide: const BorderSide(color: softLine),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(9),
                borderSide: const BorderSide(color: softLine),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(9),
                borderSide: const BorderSide(color: green),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class SocialButton extends StatelessWidget {
  const SocialButton({super.key, required this.label, required this.icon});

  final String label;
  final String icon;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: () {},
      style: OutlinedButton.styleFrom(
        foregroundColor: ink,
        side: const BorderSide(color: softLine),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(9)),
        padding: const EdgeInsets.symmetric(vertical: 14),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(icon, style: const TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(width: 10),
          Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class MenuItem extends StatelessWidget {
  const MenuItem({super.key, required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 6),
        child: Text(
          label,
          style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 15),
        ),
      ),
    );
  }
}

class ProfileSummaryCard extends StatelessWidget {
  const ProfileSummaryCard({super.key});

  @override
  Widget build(BuildContext context) {
    return CardShell(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      child: Column(
        children: [
          Row(
            children: [
              const CircleAvatar(
                radius: 34,
                backgroundColor: green,
                child: Text(
                  'AH',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Ahmed Hassan',
                        style: TextStyle(
                            fontSize: 18, fontWeight: FontWeight.w900)),
                    SizedBox(height: 5),
                    Text('ahmed.hassan@email.com',
                        style: TextStyle(color: muted, fontSize: 12)),
                  ],
                ),
              ),
              IconButton(
                onPressed: () {},
                icon: const Icon(Icons.settings_outlined, color: green),
              ),
            ],
          ),
          const Divider(height: 26),
          Row(
            children: const [
              Expanded(
                  child: ProfileMetric(
                      icon: Icons.emoji_transportation,
                      value: '127',
                      label: 'Trips',
                      color: green)),
              Expanded(
                  child: ProfileMetric(
                      icon: Icons.star_border,
                      value: '850',
                      label: 'Points',
                      color: Color(0xFFFACC15))),
              Expanded(
                  child: ProfileMetric(
                      icon: Icons.shield_outlined,
                      value: 'Gold',
                      label: 'Tier',
                      color: Color(0xFF3B82F6))),
            ],
          ),
        ],
      ),
    );
  }
}

class ProfileMetric extends StatelessWidget {
  const ProfileMetric({
    super.key,
    required this.icon,
    required this.value,
    required this.label,
    required this.color,
  });

  final IconData icon;
  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _MapPin(icon: icon, bg: color.withValues(alpha: .12), color: color),
        const SizedBox(height: 8),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
        Text(label, style: const TextStyle(color: muted, fontSize: 11)),
      ],
    );
  }
}

class ProfileSection extends StatelessWidget {
  const ProfileSection(
      {super.key, required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(
                  color: muted, fontWeight: FontWeight.w900, fontSize: 12)),
          const SizedBox(height: 10),
          CardShell(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                for (int i = 0; i < children.length; i++) ...[
                  children[i],
                  if (i != children.length - 1)
                    const Divider(height: 1, indent: 56),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ProfileSettingTile extends StatelessWidget {
  const ProfileSettingTile({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    this.onTap,
    this.blue = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final bool blue;

  @override
  Widget build(BuildContext context) {
    final color = blue ? const Color(0xFF3B82F6) : green;
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        child: Row(
          children: [
            _MapPin(
              icon: icon,
              bg: color.withValues(alpha: .12),
              color: color,
              size: 34,
              iconSize: 18,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: const TextStyle(fontWeight: FontWeight.w900)),
                  const SizedBox(height: 3),
                  Text(subtitle,
                      style: const TextStyle(color: muted, fontSize: 11)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, color: muted),
          ],
        ),
      ),
    );
  }
}

class SettingsTile extends StatelessWidget {
  const SettingsTile(
      {super.key,
      required this.icon,
      required this.title,
      this.trailing,
      this.danger = false,
      this.onTap});

  final IconData icon;
  final String title;
  final String? trailing;
  final bool danger;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return CardShell(
      onTap: onTap,
      margin: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          _MapPin(
              icon: icon,
              bg: danger ? const Color(0xFFFFEBEE) : paleGreen,
              color: danger ? rose : green),
          const SizedBox(width: 12),
          Expanded(
              child: Text(title,
                  style: TextStyle(
                      color: danger ? rose : ink,
                      fontWeight: FontWeight.w800))),
          Text(trailing ?? '', style: const TextStyle(color: muted)),
          const SizedBox(width: 4),
          const Icon(Icons.chevron_right, color: muted),
        ],
      ),
    );
  }
}

class SimpleListScreen extends StatelessWidget {
  const SimpleListScreen({
    super.key,
    required this.title,
    required this.emptyText,
    required this.onBack,
  });

  final String title;
  final String emptyText;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          color: green,
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          child: SafeArea(
            bottom: false,
            child: HeaderRow(title: title, onBack: onBack),
          ),
        ),
        Expanded(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(
                emptyText,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: muted,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
