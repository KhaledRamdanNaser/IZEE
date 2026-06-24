import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' hide Path;

import 'services/driver_services.dart';

void main() {
  runApp(const IzeeDriverApp());
}

const green = Color(0xFF12BD78);
const darkGreen = Color(0xFF079A43);
const paleGreen = Color(0xFFE9FBF2);
const ink = Color(0xFF111827);
const muted = Color(0xFF64748B);
const bg = Color(0xFFF7F9FB);
const danger = Color(0xFFF20A18);
const orange = Color(0xFFE56800);
const purple = Color(0xFF9B00F5);
const rose = Color(0xFFF43F5E);

class IzeeDriverApp extends StatefulWidget {
  const IzeeDriverApp({super.key});

  @override
  State<IzeeDriverApp> createState() => _IzeeDriverAppState();
}

class _IzeeDriverAppState extends State<IzeeDriverApp> {
  late final DriverServices services = DriverServices();

  @override
  void dispose() {
    services.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<Map<String, dynamic>>(
      valueListenable: services.appSettings,
      builder: (context, settings, _) {
        final themeModeStr = settings['theme']?.toString() ?? 'system';
        ThemeMode themeMode;
        if (themeModeStr == 'light') {
          themeMode = ThemeMode.light;
        } else if (themeModeStr == 'dark') {
          themeMode = ThemeMode.dark;
        } else {
          themeMode = ThemeMode.system;
        }

        return MaterialApp(
          title: 'IZEE Driver',
          debugShowCheckedModeBanner: false,
          themeMode: themeMode,
          theme: ThemeData(
            useMaterial3: true,
            brightness: Brightness.light,
            scaffoldBackgroundColor: bg,
            colorScheme: ColorScheme.fromSeed(seedColor: green, brightness: Brightness.light),
            fontFamily: 'Roboto',
          ),
          darkTheme: ThemeData(
            useMaterial3: true,
            brightness: Brightness.dark,
            scaffoldBackgroundColor: const Color(0xFF121212),
            colorScheme: ColorScheme.fromSeed(seedColor: green, brightness: Brightness.dark),
            fontFamily: 'Roboto',
          ),
          home: DriverLoginScreen(services: services),
        );
      },
    );
  }
}

class DriverLoginScreen extends StatefulWidget {
  const DriverLoginScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<DriverLoginScreen> createState() => _DriverLoginScreenState();
}

class _DriverLoginScreenState extends State<DriverLoginScreen> {
  final _driverIdController = TextEditingController(text: 'driver_test_001');
  final _passwordController = TextEditingController();
  bool _hidePassword = true;
  bool _loggingIn = false;
  String? _loginError;

  @override
  void dispose() {
    _driverIdController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _signIn({bool biometric = false}) async {
    if (_loggingIn) return;

    setState(() {
      _loggingIn = true;
      _loginError = null;
    });

    try {
      if (!biometric) {
        await widget.services.login(
          driverId: _driverIdController.text.trim(),
          password: _passwordController.text,
        );
      }
    } catch (error) {
      _loginError = error.toString();
    }

    if (!mounted) return;
    setState(() => _loggingIn = false);
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => DriverHomeScreen(services: widget.services),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3FCF8),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Container(
              width: double.infinity,
              padding: EdgeInsets.fromLTRB(
                24,
                MediaQuery.paddingOf(context).top + 26,
                24,
                30,
              ),
              color: darkGreen,
              child: const Column(
                children: [
                  CircleAvatar(
                    radius: 26,
                    backgroundColor: Colors.white,
                    child: Icon(Icons.directions_bus, color: Color(0xFF2563EB)),
                  ),
                  SizedBox(height: 14),
                  Text(
                    'IZEE Driver',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 25,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Welcome back!',
                    style: TextStyle(
                        color: Colors.white, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 26, 16, 26),
                children: [
                  Container(
                    padding: const EdgeInsets.fromLTRB(18, 24, 18, 20),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFFE2E8F0)),
                      boxShadow: const [
                        BoxShadow(
                          color: Color(0x1F000000),
                          blurRadius: 18,
                          offset: Offset(0, 8),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          'Secure Login',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            color: Color(0xFF1F2937),
                            fontSize: 20,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 30),
                        const LoginLabel('Driver ID / Phone Number'),
                        const SizedBox(height: 8),
                        LoginInput(
                          icon: Icons.phone_outlined,
                          hint: 'Enter your Driver ID',
                          keyboardType: TextInputType.phone,
                          controller: _driverIdController,
                        ),
                        const SizedBox(height: 18),
                        const LoginLabel('Password / PIN'),
                        const SizedBox(height: 8),
                        LoginInput(
                          icon: Icons.lock_outline,
                          hint: 'Enter your password',
                          controller: _passwordController,
                          obscureText: _hidePassword,
                          trailing: IconButton(
                            tooltip: _hidePassword
                                ? 'Show password'
                                : 'Hide password',
                            onPressed: () =>
                                setState(() => _hidePassword = !_hidePassword),
                            icon: Icon(
                              _hidePassword
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                              color: muted,
                              size: 18,
                            ),
                          ),
                        ),
                        const SizedBox(height: 36),
                        if (_loginError != null) ...[
                          Text(
                            'Login endpoint warning: $_loginError',
                            style: const TextStyle(color: danger, fontSize: 12),
                          ),
                          const SizedBox(height: 12),
                        ],
                        FilledButton(
                          onPressed: _loggingIn ? null : () => _signIn(),
                          style: FilledButton.styleFrom(
                            backgroundColor: darkGreen,
                            minimumSize: const Size.fromHeight(54),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                          child: const Text(
                            'Sign In',
                            style: TextStyle(fontWeight: FontWeight.w900),
                          ),
                        ),
                        const SizedBox(height: 34),
                        const Row(
                          children: [
                            Expanded(child: Divider()),
                            Padding(
                              padding: EdgeInsets.symmetric(horizontal: 12),
                              child: Text('Or', style: TextStyle(color: muted)),
                            ),
                            Expanded(child: Divider()),
                          ],
                        ),
                        const SizedBox(height: 20),
                        OutlinedButton.icon(
                          onPressed: _loggingIn
                              ? null
                              : () => _signIn(biometric: true),
                          style: OutlinedButton.styleFrom(
                            minimumSize: const Size.fromHeight(50),
                            foregroundColor: ink,
                            side: const BorderSide(color: Color(0xFFCBD5E1)),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(6),
                            ),
                          ),
                          icon: const Icon(Icons.fingerprint, size: 20),
                          label: const Text(
                            'Use Biometric Login',
                            style: TextStyle(fontWeight: FontWeight.w900),
                          ),
                        ),
                        const SizedBox(height: 36),
                        TextButton(
                          onPressed: () {},
                          child: const Text(
                            'Having trouble? Contact dispatch',
                            style: TextStyle(color: muted),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class LoginLabel extends StatelessWidget {
  const LoginLabel(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        color: Color(0xFF334155),
        fontWeight: FontWeight.w800,
      ),
    );
  }
}

class LoginInput extends StatelessWidget {
  const LoginInput({
    super.key,
    required this.icon,
    required this.hint,
    this.controller,
    this.keyboardType,
    this.obscureText = false,
    this.trailing,
  });

  final IconData icon;
  final String hint;
  final TextEditingController? controller;
  final TextInputType? keyboardType;
  final bool obscureText;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      obscureText: obscureText,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: const TextStyle(color: muted, fontSize: 14),
        prefixIcon: Icon(icon, color: muted, size: 20),
        suffixIcon: trailing,
        filled: true,
        fillColor: const Color(0xFFFAFBFC),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: Color(0xFFCBD5E1)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
          borderSide: const BorderSide(color: darkGreen, width: 1.4),
        ),
      ),
    );
  }
}

class DriverHomeScreen extends StatefulWidget {
  const DriverHomeScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<DriverHomeScreen> createState() => _DriverHomeScreenState();
}

class _DriverHomeScreenState extends State<DriverHomeScreen> {
  @override
  void initState() {
    super.initState();
    // Silently refresh unread count so the badge is correct on home load.
    widget.services.loadUnreadCount();
  }

  @override
  Widget build(BuildContext context) {
    final services = widget.services;
    return Scaffold(
      drawer: DriverDrawer(services: services),
      body: Column(
        children: [
          Builder(
            builder: (context) => HomeHeader(
              services: services,
              onMenu: () => Scaffold.of(context).openDrawer(),
              onProfile: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => DriverProfileScreen(services: services),
                ),
              ),
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(12, 18, 12, 28),
              children: [
                TripStatusCard(services: services),
                const SizedBox(height: 14),
                GridView.count(
                  crossAxisCount: 2,
                  mainAxisSpacing: 10,
                  crossAxisSpacing: 10,
                  childAspectRatio: .98,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  children: [
                    DashboardTile(
                      icon: Icons.map_outlined,
                      title: 'View Map',
                      subtitle: 'Live location',
                      color: const Color(0xFF2F80ED),
                      bgColor: const Color(0xFFE7F0FF),
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => LiveMapScreen(services: services),
                        ),
                      ),
                    ),
                    DashboardTile(
                      icon: Icons.pin_drop_outlined,
                      title: 'Route Info',
                      subtitle: 'Stops & ETA',
                      color: green,
                      bgColor: paleGreen,
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) =>
                              RouteInformationScreen(services: services),
                        ),
                      ),
                    ),
                    DashboardTile(
                      icon: Icons.warning_amber_rounded,
                      title: 'Report Issue',
                      subtitle: 'Quick report',
                      color: const Color(0xFFF59E0B),
                      bgColor: const Color(0xFFFFF3CD),
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (_) =>
                                ReportIssueScreen(services: services)),
                      ),
                    ),
                    // Messages tile: live unread badge
                    ValueListenableBuilder<int>(
                      valueListenable: services.unreadCount,
                      builder: (context, count, _) => DashboardTile(
                        icon: Icons.chat_bubble_outline,
                        title: 'Messages',
                        subtitle: 'From dispatch',
                        color: purple,
                        bgColor: const Color(0xFFF3E8FF),
                        badgeCount: count,
                        onTap: () async {
                          await Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (_) =>
                                    MessagesScreen(services: services)),
                          );
                          // Refresh badge after returning from messages screen.
                          if (mounted) widget.services.loadUnreadCount();
                        },
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                NextStopCard(services: services),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class HomeHeader extends StatelessWidget {
  const HomeHeader({
    super.key,
    required this.services,
    required this.onMenu,
    required this.onProfile,
  });

  final DriverServices services;
  final VoidCallback onMenu;
  final VoidCallback onProfile;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.fromLTRB(
          12, MediaQuery.paddingOf(context).top + 10, 14, 18),
      decoration: const BoxDecoration(
        color: darkGreen,
        boxShadow: [BoxShadow(color: Color(0x33000000), blurRadius: 16)],
      ),
      child: Row(
        children: [
          IconButton(
            onPressed: onMenu,
            icon: const Icon(Icons.menu, color: Colors.white),
          ),
          const SizedBox(width: 4),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'IZEE Driver',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                SizedBox(height: 2),
                Text('Ahmed Hassan', style: TextStyle(color: Colors.white)),
              ],
            ),
          ),
          // Profile avatar — no badge here (badge lives on the Messages tile)
          InkWell(
            onTap: onProfile,
            customBorder: const CircleBorder(),
            child: const CircleAvatar(
              radius: 22,
              backgroundColor: Colors.white,
              child: Icon(Icons.person, color: Color(0xFF4C1D95)),
            ),
          ),
        ],
      ),
    );
  }
}

class DriverDrawer extends StatelessWidget {
  const DriverDrawer({super.key, required this.services});

  final DriverServices services;

  @override
  Widget build(BuildContext context) {
    return Drawer(
      backgroundColor: Colors.white,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  CircleAvatar(
                    radius: 22,
                    backgroundColor: green,
                    child: Icon(Icons.directions_bus, color: Colors.white),
                  ),
                  SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'IZEE Transit',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w900),
                        ),
                        Text('Smart City Transport',
                            style: TextStyle(color: muted)),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 34),
              DrawerItem(
                icon: Icons.route,
                label: 'My Trips',
                onTap: () {
                  Navigator.pop(context);
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => MyTripsScreen(services: services),
                    ),
                  );
                },
              ),
              DrawerItem(
                icon: Icons.history,
                label: 'Trip History',
                onTap: () {
                  Navigator.pop(context);
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => TripHistoryScreen(services: services),
                    ),
                  );
                },
              ),
              DrawerItem(
                icon: Icons.support_agent,
                label: 'Help & Support',
                onTap: () {
                  Navigator.pop(context);
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ReportIssueScreen(services: services),
                    ),
                  );
                },
              ),
              DrawerItem(
                icon: Icons.settings_outlined,
                label: 'Settings',
                onTap: () {
                  Navigator.pop(context);
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => DriverSettingsScreen(services: services),
                    ),
                  );
                },
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.close),
                label: const Text('Close'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class DrawerItem extends StatelessWidget {
  const DrawerItem(
      {super.key, required this.icon, required this.label, this.onTap});

  final IconData icon;
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(4),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 4),
        child: Row(
          children: [
            Icon(icon, color: muted, size: 20),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                label,
                style: const TextStyle(fontWeight: FontWeight.w800),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class TripStatusCard extends StatelessWidget {
  const TripStatusCard({super.key, required this.services});

  final DriverServices services;

  @override
  Widget build(BuildContext context) {
    return CardShell(
      borderColor: green,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Current Trip Status',
                      style: TextStyle(color: muted, fontSize: 12),
                    ),
                    SizedBox(height: 6),
                    Row(
                      children: [
                        CircleAvatar(radius: 5, backgroundColor: green),
                        SizedBox(width: 8),
                        Text(
                          'Trip Active',
                          style: TextStyle(
                              fontSize: 20, fontWeight: FontWeight.w800),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const StatusPill(label: 'On Time'),
            ],
          ),
          const SizedBox(height: 24),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFFFAFBFC),
              borderRadius: BorderRadius.circular(8),
            ),
            child: ValueListenableBuilder<DriverTripState>(
              valueListenable: services.tripState,
              builder: (context, state, _) {
                return Row(
                  children: [
                    Expanded(
                        child: InfoPair(label: 'Route', value: state.active && state.routeId.isNotEmpty ? state.routeId : 'no routes active')),
                    Expanded(
                        child: InfoPair(
                            label: 'Vehicle ID', value: state.vehicleId)),
                  ],
                );
              },
            ),
          ),
          const SizedBox(height: 22),
          const Row(
            children: [
              Icon(Icons.access_time, size: 18, color: muted),
              SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Started at 08:15 AM • 2h 15m elapsed',
                  style: TextStyle(color: muted),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          SizedBox(
            height: 54,
            width: double.infinity,
            child: ValueListenableBuilder<DriverTripState>(
              valueListenable: services.tripState,
              builder: (context, state, _) {
                final active = state.active;
                return FilledButton.icon(
                  style: FilledButton.styleFrom(
                    backgroundColor: active ? danger : darkGreen,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(7)),
                  ),
                  onPressed: state.sending
                      ? null
                      : () async {
                          try {
                            if (active) {
                              await services.endTrip();
                            } else {
                              await services.startTrip();
                            }
                          } catch (error) {
                            if (!context.mounted) return;
                            showAppPopup(
                              context,
                              message: error.toString().replaceFirst('Exception: ', ''),
                              isSuccess: false,
                            );
                          }
                        },
                  icon: Icon(active ? Icons.stop : Icons.play_arrow, size: 16),
                  label: Text(
                    active ? 'End Trip' : 'Start Trip',
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class InfoPair extends StatelessWidget {
  const InfoPair({super.key, required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: muted, fontSize: 12)),
        const SizedBox(height: 5),
        Text(value,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
      ],
    );
  }
}

class DashboardTile extends StatelessWidget {
  const DashboardTile({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    required this.bgColor,
    required this.onTap,
    this.badgeCount = 0,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final Color bgColor;
  final VoidCallback onTap;
  /// When > 0, shows a red badge on the top-right corner of the tile.
  final int badgeCount;

  @override
  Widget build(BuildContext context) {
    // Badge sits on the icon circle, not the card corner.
    final iconWidget = Stack(
      clipBehavior: Clip.none,
      children: [
        CircleAvatar(
          backgroundColor: bgColor,
          child: Icon(icon, color: color),
        ),
        if (badgeCount > 0)
          Positioned(
            right: -5,
            top: -5,
            child: Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: Colors.red,
                shape: BoxShape.circle,
                border: Border.all(color: Colors.white, width: 1.5),
              ),
              constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
              child: Text(
                badgeCount > 99 ? '99+' : '$badgeCount',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 9,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
          ),
      ],
    );

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: CardShell(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            iconWidget,
            const Spacer(),
            Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 16),
            Text(subtitle, style: const TextStyle(color: muted, fontSize: 12)),
          ],
        ),
      ),
    );
  }
}

class NextStopCard extends StatelessWidget {
  const NextStopCard({super.key, required this.services});

  final DriverServices services;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<Map<String, dynamic>?>(
      valueListenable: services.routeState,
      builder: (context, routeData, _) {
        if (routeData == null) {
          return Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: const Color(0xFFFAFBFC),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Row(
              children: [
                CircleAvatar(
                  backgroundColor: const Color(0xFFF1F5F9),
                  child: const Icon(Icons.info_outline, color: muted),
                ),
                const SizedBox(width: 14),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'no routes active',
                        style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            color: ink),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'Start a trip to see next stop details.',
                        style: TextStyle(color: muted, fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        }

        final routeInfo = DriverRouteInfo.fromApi(routeData);
        if (routeInfo.isComplete) {
          return Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: const Color(0xFFE0F2FE),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFBAE6FD)),
            ),
            child: Row(
              children: [
                const CircleAvatar(
                  backgroundColor: Color(0xFFBAE6FD),
                  child: Icon(Icons.check_circle_outline,
                      color: Color(0xFF0284C7)),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Route Completed',
                        style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            color: ink),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Arrived at ${routeInfo.destination}.',
                        style: const TextStyle(color: muted, fontSize: 13),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        }

        final nextStop = routeInfo.stops.firstWhere(
          (s) => s.current,
          orElse: () => routeInfo.stops.firstWhere(
            (s) => !s.completed,
            orElse: () => routeInfo.stops.last,
          ),
        );

        final scheduledTimeText = nextStop.time;
        final timeParts = scheduledTimeText.split(' ');
        final timeNum = timeParts.isNotEmpty ? timeParts[0] : '';
        final timeAmpm = timeParts.length > 1 ? timeParts[1] : '';

        return InkWell(
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => RouteInformationScreen(services: services),
              ),
            );
          },
          borderRadius: BorderRadius.circular(8),
          child: Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: const Color(0xFFE6FFF1),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFF9DECC3)),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x0F000000),
                  blurRadius: 8,
                  offset: Offset(0, 2),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text(
                      'Next Stop',
                      style: TextStyle(
                          color: muted,
                          fontWeight: FontWeight.w600,
                          fontSize: 12),
                    ),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: green.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.directions_bus,
                              size: 12, color: darkGreen),
                          SizedBox(width: 4),
                          Text(
                            'ON TRIP',
                            style: TextStyle(
                              color: darkGreen,
                              fontSize: 10,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            nextStop.name,
                            style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                                color: ink),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'ETA: ${nextStop.etaMinutes} mins • ${nextStop.distance}',
                            style: const TextStyle(color: muted),
                          ),
                        ],
                      ),
                    ),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(
                          timeNum,
                          style: const TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.w800,
                              color: ink),
                        ),
                        const SizedBox(width: 2),
                        Text(
                          timeAmpm,
                          style: const TextStyle(
                              color: muted,
                              fontSize: 12,
                              fontWeight: FontWeight.w600),
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class DriverProfileScreen extends StatelessWidget {
  const DriverProfileScreen({super.key, required this.services});

  final DriverServices services;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          GreenTopBar(
              title: 'Driver Profile', onBack: () => Navigator.pop(context)),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(12),
              children: [
                const ProfileHero(),
                const SectionTitle('Personal Information'),
                const CardShell(
                  child: Column(
                    children: [
                      SettingRow(
                        icon: Icons.badge_outlined,
                        title: 'Driver ID',
                        subtitle: 'DRV-2020-1234',
                      ),
                      SettingRow(
                        icon: Icons.phone_outlined,
                        title: 'Phone Number',
                        subtitle: '+20 100 123 4567',
                      ),
                      SettingRow(
                        icon: Icons.location_on_outlined,
                        title: 'Base Station',
                        subtitle: 'Downtown Terminal, Cairo',
                      ),
                    ],
                  ),
                ),
                const SectionTitle('Assigned Vehicle'),
                const VehicleCard(),
                const SectionTitle('Settings'),
                const CardShell(
                  child: Column(
                    children: [
                      ToggleRow(
                        icon: Icons.location_on_outlined,
                        title: 'Location Sharing',
                        subtitle: 'Share real-time location',
                      ),
                      ToggleRow(
                        icon: Icons.notifications_none,
                        title: 'Push Notifications',
                        subtitle: 'Receive alerts & updates',
                      ),
                    ],
                  ),
                ),
                const SectionTitle('This Month'),
                const MonthStats(),
                const SizedBox(height: 20),
                const OutlineAction(
                    icon: Icons.settings_outlined, label: 'App Settings'),
                const SizedBox(height: 10),
                OutlineAction(
                  icon: Icons.logout,
                  label: 'Logout',
                  red: true,
                  onPressed: () async {
                    await services.logout();
                    if (!context.mounted) return;
                    Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute(
                        builder: (_) => DriverLoginScreen(services: services),
                      ),
                      (route) => false,
                    );
                  },
                ),
                const SizedBox(height: 24),
                const Center(
                  child: Text('IZEE Driver App v2.1.0',
                      style: TextStyle(color: muted)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ProfileHero extends StatelessWidget {
  const ProfileHero({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF18AB52),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        children: [
          CircleAvatar(
            radius: 32,
            backgroundColor: Colors.white,
            child: Icon(Icons.person, color: Color(0xFF4C1D95), size: 34),
          ),
          SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Ahmed Hassan',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                ),
                SizedBox(height: 4),
                Text('Driver since 2020',
                    style: TextStyle(color: Colors.white)),
                SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [StatusPill(label: 'Verified'), RatingPill()],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class VehicleCard extends StatelessWidget {
  const VehicleCard({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardShell(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              CircleAvatar(
                backgroundColor: paleGreen,
                child: Icon(Icons.directions_bus, color: Color(0xFF2563EB)),
              ),
              SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('BUS-4521',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                  Text('Mercedes-Benz Citaro', style: TextStyle(color: muted)),
                ],
              ),
            ],
          ),
          SizedBox(height: 28),
          Row(
            children: [
              Expanded(
                  child: InfoPair(label: 'Capacity', value: '80 passengers')),
              Expanded(child: InfoPair(label: 'Status', value: 'Active')),
            ],
          ),
        ],
      ),
    );
  }
}

class LiveMapScreen extends StatefulWidget {
  const LiveMapScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<LiveMapScreen> createState() => _LiveMapScreenState();
}

class _LiveMapScreenState extends State<LiveMapScreen> {
  bool _loadingRoute = false;
  final MapController _mapController = MapController();

  @override
  void initState() {
    super.initState();
    if (widget.services.routeState.value == null) {
      _loadRoute();
    }
  }

  Future<void> _loadRoute() async {
    setState(() => _loadingRoute = true);
    try {
      await widget.services.loadRouteInfo();
    } catch (e) {
      debugPrint('MAP_ROUTE_LOAD_RESPONSE_ERROR: $e');
    } finally {
      if (mounted) setState(() => _loadingRoute = false);
    }
  }

  void _zoomMap(double delta) {
    final camera = _mapController.camera;
    final nextZoom = (camera.zoom + delta).clamp(10.0, 18.0).toDouble();
    _mapController.move(camera.center, nextZoom);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          PlainTopBar(title: 'Live Map', onBack: () => Navigator.pop(context)),
          Expanded(
            child: Stack(
              children: [
                Positioned.fill(
                  child: ValueListenableBuilder<Map<String, dynamic>?>(
                    valueListenable: widget.services.routeState,
                    builder: (context, routeData, _) {
                      return ValueListenableBuilder<DriverTripState>(
                        valueListenable: widget.services.tripState,
                        builder: (context, tripState, __) {
                          final route = routeData == null
                              ? null
                              : DriverRouteInfo.fromApi(routeData);
                          final position = tripState.lastPosition;
                          return DriverMapCanvas(
                            mapController: _mapController,
                            route: route,
                            vehicleLat: position?.latitude,
                            vehicleLon: position?.longitude,
                          );
                        },
                      );
                    },
                  ),
                ),
                Positioned.fill(
                  child: IgnorePointer(
                    child: ValueListenableBuilder<Map<String, dynamic>?>(
                      valueListenable: widget.services.routeState,
                      builder: (context, routeData, _) {
                        final route = routeData == null
                            ? null
                            : DriverRouteInfo.fromApi(routeData);
                        if (_loadingRoute || route == null || route.hasRoutePath) {
                          return const SizedBox.shrink();
                        }
                        return const _MapNotice(
                          message: 'Route path not available',
                        );
                      },
                    ),
                  ),
                ),
                Positioned.fill(
                  child: IgnorePointer(
                    child: ValueListenableBuilder<DriverTripState>(
                      valueListenable: widget.services.tripState,
                      builder: (context, tripState, _) {
                        return ValueListenableBuilder<Map<String, dynamic>?>(
                          valueListenable: widget.services.routeState,
                          builder: (context, routeData, __) {
                            if (_loadingRoute ||
                                routeData != null ||
                                tripState.lastError == null) {
                              return const SizedBox.shrink();
                            }
                            return _MapNotice(message: tripState.lastError!);
                          },
                        );
                      },
                    ),
                  ),
                ),
                Positioned(
                  top: 12,
                  left: 12,
                  right: 12,
                  child: ValueListenableBuilder<DriverTripState>(
                    valueListenable: widget.services.tripState,
                    builder: (context, state, _) => Column(
                      children: [
                        MapStatusCard(
                          icon: Icons.sensors,
                          title: 'Location Sharing',
                          subtitle: state.active ? 'Active' : 'Inactive',
                          toggle: true,
                        ),
                        const SizedBox(height: 10),
                        MapStatusCard(
                          icon: Icons.speed,
                          title: _speedText(state),
                          subtitle: 'Current Speed',
                        ),
                        const SizedBox(height: 10),
                        ValueListenableBuilder<Map<String, dynamic>?>(
                          valueListenable: widget.services.routeState,
                          builder: (context, routeData, __) {
                            final route = routeData == null
                                ? null
                                : DriverRouteInfo.fromApi(routeData);
                            final subtitle = route == null
                                ? 'Stops & ETA'
                                : route.hasRoutePath
                                    ? '${route.stops.length} stops - ${route.origin} to ${route.destination}'
                                    : 'Route path not available';
                            return MapStatusCard(
                              icon: Icons.route_outlined,
                              title: _loadingRoute
                                  ? 'Loading assigned route'
                                  : route?.routeName ?? 'No assigned route',
                              subtitle: subtitle,
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                ),
                Positioned(
                  right: 16,
                  bottom: 214 + MediaQuery.paddingOf(context).bottom,
                  child: MapZoomButtons(
                    onZoomIn: () => _zoomMap(.25),
                    onZoomOut: () => _zoomMap(-.25),
                  ),
                ),
                Positioned(
                  left: 12,
                  right: 12,
                  bottom: 24 + MediaQuery.paddingOf(context).bottom,
                  child: CurrentLocationPanel(services: widget.services),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String _speedText(DriverTripState state) {
  final speed = state.lastPosition?.speed;
  if (speed == null || !speed.isFinite || speed < 0) return '0 km/h';
  return '${(speed * 3.6).round()} km/h';
}

class DriverMapCanvas extends StatelessWidget {
  const DriverMapCanvas({
    super.key,
    required this.mapController,
    this.route,
    this.vehicleLat,
    this.vehicleLon,
  });

  final MapController mapController;
  final DriverRouteInfo? route;
  final double? vehicleLat;
  final double? vehicleLon;

  @override
  Widget build(BuildContext context) {
    final stopPoints = _routeStopPoints;
    final routeLine =
        route?.geometry.isNotEmpty == true ? route!.geometry : stopPoints;
    final vehiclePoint = _vehiclePoint;
    final center = vehiclePoint ??
        (routeLine.isNotEmpty
            ? routeLine[routeLine.length ~/ 2]
            : const LatLng(30.0444, 31.2357));

    return FlutterMap(
      mapController: mapController,
      options: MapOptions(
        initialCenter: center,
        initialZoom: stopPoints.length > 3 ? 11.5 : 13,
        minZoom: 10,
        maxZoom: 18,
        interactionOptions: const InteractionOptions(
          flags: InteractiveFlag.drag |
              InteractiveFlag.flingAnimation |
              InteractiveFlag.pinchMove |
              InteractiveFlag.pinchZoom |
              InteractiveFlag.doubleTapZoom |
              InteractiveFlag.scrollWheelZoom,
        ),
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.example.izee_driver',
        ),
        if (routeLine.length >= 2)
          Builder(
            builder: (context) {
              final completedStops = route?.stops.where((s) => s.completed && s.hasCoordinates) ?? const [];
              final lastCompletedStop = completedStops.isNotEmpty ? completedStops.last : null;
              if (lastCompletedStop == null) {
                return PolylineLayer(
                  polylines: [
                    Polyline(
                      points: routeLine,
                      strokeWidth: 6,
                      color: green.withOpacity(.85),
                    ),
                  ],
                );
              }
              final splitIndex = _findClosestPointIndex(
                routeLine,
                lastCompletedStop.lat,
                lastCompletedStop.lon,
              );
              final completedPoints = routeLine.sublist(0, splitIndex + 1);
              final remainingPoints = routeLine.sublist(splitIndex);
              return PolylineLayer(
                polylines: [
                  if (completedPoints.length >= 2)
                    Polyline(
                      points: completedPoints,
                      strokeWidth: 6,
                      color: const Color(0xFF94A3B8).withOpacity(0.85),
                    ),
                  if (remainingPoints.length >= 2)
                    Polyline(
                      points: remainingPoints,
                      strokeWidth: 6,
                      color: green.withOpacity(.85),
                    ),
                ],
              );
            },
          ),
        if (stopPoints.isNotEmpty || vehiclePoint != null)
          MarkerLayer(
            markers: [
              for (final stop
                  in (route?.stops ?? const <DriverStop>[])
                      .where((stop) => stop.hasCoordinates))
                Marker(
                  point: LatLng(stop.lat, stop.lon),
                  width: stop.current ? 44 : 34,
                  height: stop.current ? 44 : 34,
                  child: _MapStopMarker(stop: stop),
                ),
              if (vehiclePoint != null)
                Marker(
                  point: vehiclePoint,
                  width: 58,
                  height: 58,
                  child: const _VehicleMapMarker(),
                ),
            ],
          ),
      ],
    );
  }

  List<LatLng> get _routeStopPoints {
    return route?.stops
            .where((stop) => stop.hasCoordinates)
            .map((stop) => LatLng(stop.lat, stop.lon))
            .toList(growable: false) ??
        const <LatLng>[];
  }

  LatLng? get _vehiclePoint {
    if (vehicleLat == null || vehicleLon == null) return null;
    if (!vehicleLat!.isFinite || !vehicleLon!.isFinite) return null;
    return LatLng(vehicleLat!, vehicleLon!);
  }

  int _findClosestPointIndex(List<LatLng> points, double lat, double lon) {
    int closestIndex = 0;
    double minDistanceSq = double.infinity;
    for (int i = 0; i < points.length; i++) {
      final p = points[i];
      final dLat = p.latitude - lat;
      final dLon = p.longitude - lon;
      final distSq = dLat * dLat + dLon * dLon;
      if (distSq < minDistanceSq) {
        minDistanceSq = distSq;
        closestIndex = i;
      }
    }
    return closestIndex;
  }
}

class _MapStopMarker extends StatelessWidget {
  const _MapStopMarker({required this.stop});

  final DriverStop stop;

  @override
  Widget build(BuildContext context) {
    final color = stop.current
        ? const Color(0xFF2563EB)
        : stop.completed
            ? green
            : Colors.white;
    final border =
        stop.current || stop.completed ? color : muted.withOpacity(.65);
    return DecoratedBox(
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color,
        border: Border.all(color: border, width: 3),
        boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 8)],
      ),
      child: Icon(
        stop.current ? Icons.flag : Icons.circle,
        size: stop.current ? 18 : 10,
        color: stop.current || stop.completed ? Colors.white : muted,
      ),
    );
  }
}

class _VehicleMapMarker extends StatelessWidget {
  const _VehicleMapMarker();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: green.withOpacity(.22),
      ),
      alignment: Alignment.center,
      child: Container(
        width: 34,
        height: 34,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: green,
          boxShadow: [BoxShadow(color: Color(0x33000000), blurRadius: 8)],
        ),
        child: const Icon(Icons.navigation, color: Colors.white, size: 21),
      ),
    );
  }
}

class _MapNotice extends StatelessWidget {
  const _MapNotice({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 32),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(.94),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFFE2E8F0)),
          boxShadow: const [
            BoxShadow(
              color: Color(0x22000000),
              blurRadius: 14,
              offset: Offset(0, 6),
            ),
          ],
        ),
        child: Text(
          message,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: muted,
            fontWeight: FontWeight.w800,
          ),
        ),
      ),
    );
  }
}

class DriverMapPainter extends CustomPainter {
  DriverMapPainter({
    this.route,
    this.vehicleLat,
    this.vehicleLon,
    this.zoom = 1,
    this.pan = Offset.zero,
  });

  final DriverRouteInfo? route;
  final double? vehicleLat;
  final double? vehicleLon;
  final double zoom;
  final Offset pan;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = const Color(0xFFEFFDF8),
    );

    canvas.save();
    canvas.translate(size.width / 2 + pan.dx, size.height / 2 + pan.dy);
    canvas.scale(zoom);
    canvas.translate(-size.width / 2, -size.height / 2);

    final grid = Paint()
      ..color = const Color(0xFFD9EFE9)
      ..strokeWidth = 1;
    for (double x = 0; x < size.width; x += 28) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid);
    }
    for (double y = 0; y < size.height; y += 28) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }

    final road = Paint()
      ..color = const Color(0xFFD9E4E8)
      ..strokeWidth = 54;
    canvas.drawLine(Offset(size.width * .56, 0),
        Offset(size.width * .56, size.height), road);
    canvas.drawLine(Offset(0, size.height * .48),
        Offset(size.width, size.height * .48), road);

    final stops = route?.stops
            .where((stop) => stop.hasCoordinates)
            .toList(growable: false) ??
        const <DriverStop>[];
    final routePaint = Paint()
      ..color = green
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke;
    final completedPaint = Paint()
      ..color = green.withOpacity(.85)
      ..strokeWidth = 5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    final upcomingPaint = Paint()
      ..color = muted.withOpacity(.35)
      ..strokeWidth = 4
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    if (stops.length >= 2) {
      final points = _projectStops(stops, size);
      final path = Path()..moveTo(points.first.dx, points.first.dy);
      for (final point in points.skip(1)) {
        path.lineTo(point.dx, point.dy);
      }
      canvas.drawPath(path, upcomingPaint);

      final currentIndex = stops.indexWhere((stop) => stop.current);
      final completedCount = currentIndex == -1
          ? stops.where((stop) => stop.completed).length
          : currentIndex + 1;
      if (completedCount > 1) {
        final donePath = Path()..moveTo(points.first.dx, points.first.dy);
        for (final point in points.take(completedCount).skip(1)) {
          donePath.lineTo(point.dx, point.dy);
        }
        canvas.drawPath(donePath, completedPaint);
      }

      for (var i = 0; i < stops.length; i++) {
        final stop = stops[i];
        final point = points[i];
        final color = stop.current
            ? const Color(0xFF2563EB)
            : stop.completed
                ? green
                : Colors.white;
        final border =
            stop.current || stop.completed ? color : muted.withOpacity(.45);
        canvas.drawCircle(point, stop.current ? 8 : 6, Paint()..color = color);
        canvas.drawCircle(
          point,
          stop.current ? 8 : 6,
          Paint()
            ..color = border
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2,
        );
      }

      final vehiclePoint = _projectVehicle(stops, size) ??
          (points.isNotEmpty
              ? points[(completedCount - 1).clamp(0, points.length - 1).toInt()]
              : null);
      if (vehiclePoint != null) {
        _drawVehicle(canvas, vehiclePoint);
      }
    } else {
      final path = Path()
        ..moveTo(size.width * .18, size.height * .13)
        ..quadraticBezierTo(size.width * .55, size.height * .22,
            size.width * .94, size.height * .34);
      canvas.drawPath(path, routePaint);
    }

    canvas.restore();
  }

  List<Offset> _projectStops(List<DriverStop> stops, Size size) {
    final minLat = stops.map((s) => s.lat).reduce((a, b) => a < b ? a : b);
    final maxLat = stops.map((s) => s.lat).reduce((a, b) => a > b ? a : b);
    final minLon = stops.map((s) => s.lon).reduce((a, b) => a < b ? a : b);
    final maxLon = stops.map((s) => s.lon).reduce((a, b) => a > b ? a : b);
    final latRange = (maxLat - minLat).abs() < .0001 ? .0001 : maxLat - minLat;
    final lonRange = (maxLon - minLon).abs() < .0001 ? .0001 : maxLon - minLon;
    final left = size.width * .12;
    final top = size.height * .18;
    final width = size.width * .76;
    final height = size.height * .46;

    return stops.map((stop) {
      final x = left + ((stop.lon - minLon) / lonRange) * width;
      final y = top + (1 - ((stop.lat - minLat) / latRange)) * height;
      return Offset(x, y);
    }).toList(growable: false);
  }

  Offset? _projectVehicle(List<DriverStop> stops, Size size) {
    if (vehicleLat == null || vehicleLon == null || stops.isEmpty) return null;
    final minLat = stops.map((s) => s.lat).reduce((a, b) => a < b ? a : b);
    final maxLat = stops.map((s) => s.lat).reduce((a, b) => a > b ? a : b);
    final minLon = stops.map((s) => s.lon).reduce((a, b) => a < b ? a : b);
    final maxLon = stops.map((s) => s.lon).reduce((a, b) => a > b ? a : b);
    if (vehicleLat! < minLat - .02 ||
        vehicleLat! > maxLat + .02 ||
        vehicleLon! < minLon - .02 ||
        vehicleLon! > maxLon + .02) {
      return null;
    }

    final latRange = (maxLat - minLat).abs() < .0001 ? .0001 : maxLat - minLat;
    final lonRange = (maxLon - minLon).abs() < .0001 ? .0001 : maxLon - minLon;
    final left = size.width * .12;
    final top = size.height * .18;
    final width = size.width * .76;
    final height = size.height * .46;
    final x = left + ((vehicleLon! - minLon) / lonRange) * width;
    final y = top + (1 - ((vehicleLat! - minLat) / latRange)) * height;
    return Offset(x, y);
  }

  void _drawVehicle(Canvas canvas, Offset point) {
    canvas.drawCircle(point, 18, Paint()..color = green.withOpacity(.22));
    canvas.drawCircle(point, 11, Paint()..color = green);
    final arrow = Path()
      ..moveTo(point.dx, point.dy - 7)
      ..lineTo(point.dx + 6, point.dy + 6)
      ..lineTo(point.dx, point.dy + 3)
      ..lineTo(point.dx - 6, point.dy + 6)
      ..close();
    canvas.drawPath(arrow, Paint()..color = Colors.white);
  }

  @override
  bool shouldRepaint(covariant DriverMapPainter oldDelegate) {
    return oldDelegate.route != route ||
        oldDelegate.vehicleLat != vehicleLat ||
        oldDelegate.vehicleLon != vehicleLon ||
        oldDelegate.zoom != zoom ||
        oldDelegate.pan != pan;
  }
}

class CurrentBusMarker extends StatelessWidget {
  const CurrentBusMarker({super.key, this.live = false});

  final bool live;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 84,
      height: 84,
      decoration:
          BoxDecoration(shape: BoxShape.circle, color: green.withOpacity(.2)),
      alignment: Alignment.center,
      child: Container(
        width: 38,
        height: 38,
        decoration: const BoxDecoration(
          shape: BoxShape.circle,
          color: green,
          boxShadow: [BoxShadow(color: Color(0x33000000), blurRadius: 8)],
        ),
        child: Icon(live ? Icons.navigation : Icons.directions_bus,
            color: Colors.white),
      ),
    );
  }
}

class RouteInformationScreen extends StatefulWidget {
  const RouteInformationScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<RouteInformationScreen> createState() => _RouteInformationScreenState();
}

class _RouteInformationScreenState extends State<RouteInformationScreen> {
  bool _loading = false;
  bool _advancing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    if (widget.services.routeState.value == null) {
      _loadRoute();
    }
  }

  Future<void> _loadRoute() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await widget.services.loadRouteInfo();
    } catch (e) {
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  Future<void> _advanceStop() async {
    if (_advancing) return;
    setState(() => _advancing = true);

    try {
      await widget.services.advanceRouteStop();
      if (!mounted) return;
      final routeData = widget.services.routeState.value;
      if (routeData != null) {
        final updated = DriverRouteInfo.fromApi(routeData);
        if (updated.isComplete) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => TripSummaryScreen(
                services: widget.services,
                routeInfo: updated,
              ),
            ),
          );
        }
      }
    } catch (error) {
      if (!mounted) return;
      showAppPopup(
        context,
        message: error.toString().replaceFirst('Exception: ', ''),
        isSuccess: false,
      );
    } finally {
      if (mounted) setState(() => _advancing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: ValueListenableBuilder<Map<String, dynamic>?>(
        valueListenable: widget.services.routeState,
        builder: (context, routeData, _) {
          final route =
              routeData != null ? DriverRouteInfo.fromApi(routeData) : null;
          final stops = route?.stops ?? const <DriverStop>[];
          return Column(
            children: [
              GreenRouteHeader(
                onBack: () => Navigator.pop(context),
                route: route,
                loading: _loading,
              ),
              Expanded(
                child: Builder(
                  builder: (context) {
                    if (_loading && routeData == null) {
                      return const Center(
                          child: CircularProgressIndicator(color: green));
                    }
                    if (_error != null && routeData == null) {
                      return ListView(
                        padding: const EdgeInsets.all(12),
                        children: [
                          CardShell(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'Could not load route information',
                                  style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w900),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  _error!,
                                  style: const TextStyle(color: muted),
                                ),
                                const SizedBox(height: 12),
                                ElevatedButton(
                                  onPressed: _loadRoute,
                                  child: const Text('Retry'),
                                ),
                              ],
                            ),
                          ),
                        ],
                      );
                    }
                    if (stops.isEmpty) {
                      return const Center(
                          child: Text('No stops assigned yet.'));
                    }

                    return ListView.separated(
                      padding: const EdgeInsets.all(12),
                      itemCount: stops.length + 1,
                      separatorBuilder: (_, __) => const SizedBox(height: 10),
                      itemBuilder: (context, index) {
                        if (index == stops.length) {
                          final activeRoute = route!;
                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              ElevatedButton.icon(
                                onPressed: activeRoute.status == 'completed'
                                    ? null
                                    : () {
                                        Navigator.push(
                                          context,
                                          MaterialPageRoute(
                                            builder: (_) => DriverNavigationScreen(
                                              services: widget.services,
                                            ),
                                          ),
                                        );
                                      },
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: green,
                                  foregroundColor: Colors.white,
                                  minimumSize: const Size.fromHeight(48),
                                  shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(8)),
                                ),
                                icon: const Icon(Icons.navigation_outlined),
                                label: const Text('Start Navigation'),
                              ),
                              const SizedBox(height: 10),
                              OutlinedButton.icon(
                                onPressed: activeRoute.status == 'completed' || _advancing
                                    ? null
                                    : _advanceStop,
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: green,
                                  side: const BorderSide(color: green),
                                  minimumSize: const Size.fromHeight(48),
                                  shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(8)),
                                ),
                                icon: _advancing
                                    ? const SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: green,
                                        ),
                                      )
                                    : const Icon(Icons.check_circle_outline),
                                label: Text(activeRoute.status == 'completed'
                                    ? 'Route Completed'
                                    : 'Mark Next Stop Completed'),
                              ),
                            ],
                          );
                        }

                        return StopTimelineCard(
                          stop: stops[index],
                          number: index + 1,
                        );
                      },
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class DriverNavigationScreen extends StatefulWidget {
  const DriverNavigationScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<DriverNavigationScreen> createState() => _DriverNavigationScreenState();
}

class _DriverNavigationScreenState extends State<DriverNavigationScreen> {
  final MapController _mapController = MapController();
  bool _loading = false;
  bool _advancing = false;
  bool _followUser = true;
  bool _showStopsList = false;

  @override
  void initState() {
    super.initState();
    if (widget.services.routeState.value == null) {
      _loadRoute();
    }
  }

  Future<void> _loadRoute() async {
    setState(() {
      _loading = true;
    });
    try {
      await widget.services.loadRouteInfo();
    } catch (e) {
      debugPrint('Error loading route: $e');
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  Future<void> _advanceStop() async {
    if (_advancing) return;
    setState(() => _advancing = true);

    try {
      await widget.services.advanceRouteStop();
      // If route is now complete, navigate to the summary screen.
      if (!mounted) return;
      final routeData = widget.services.routeState.value;
      if (routeData != null) {
        final updated = DriverRouteInfo.fromApi(routeData);
        if (updated.isComplete) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => TripSummaryScreen(
                services: widget.services,
                routeInfo: updated,
              ),
            ),
          );
        }
      }
    } catch (error) {
      if (!mounted) return;
      showAppPopup(
        context,
        message: error.toString().replaceFirst('Exception: ', ''),
        isSuccess: false,
      );
    } finally {
      if (mounted) setState(() => _advancing = false);
    }
  }

  Widget _buildStopMarker(DriverStop stop) {
    Color borderCol;
    Color bgCol;
    double size;
    Widget? childWidget;

    if (stop.completed) {
      borderCol = Colors.grey;
      bgCol = Colors.grey.shade300;
      size = 12.0;
      childWidget = const Icon(Icons.check, size: 8, color: Colors.grey);
    } else if (stop.current) {
      borderCol = Colors.orange.shade700;
      bgCol = Colors.orange.shade100;
      size = 18.0;
      childWidget = Container(
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: Colors.orange.shade700,
        ),
        margin: const EdgeInsets.all(3),
      );
    } else {
      borderCol = Colors.blue.shade700;
      bgCol = Colors.white;
      size = 14.0;
    }

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: bgCol,
        border: Border.all(color: borderCol, width: 2),
      ),
      child: childWidget,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: ValueListenableBuilder<Map<String, dynamic>?>(
        valueListenable: widget.services.routeState,
        builder: (context, routeData, _) {
          return ValueListenableBuilder<DriverTripState>(
            valueListenable: widget.services.tripState,
            builder: (context, tripState, _) {
              final route = routeData != null ? DriverRouteInfo.fromApi(routeData) : null;
              final stops = route?.stops ?? const <DriverStop>[];
              final position = tripState.lastPosition;
              final userLocation = position != null ? LatLng(position.latitude, position.longitude) : null;
              final userHeading = position?.heading;

              if (_loading && routeData == null) {
                return const Center(
                  child: CircularProgressIndicator(color: green),
                );
              }

              if (route == null || stops.isEmpty) {
                return Stack(
                  children: [
                    Positioned(
                      top: MediaQuery.of(context).padding.top + 10,
                      left: 16,
                      child: FloatingActionButton.small(
                        heroTag: 'exit_route_info_empty',
                        backgroundColor: Colors.white,
                        foregroundColor: ink,
                        onPressed: () => Navigator.pop(context),
                        child: const Icon(Icons.close),
                      ),
                    ),
                    const Center(
                      child: Text(
                        'no routes active',
                        style: TextStyle(
                          color: muted,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                );
              }

              final activeRoute = route;

              // Determine current instruction and next stop
              String currentInstruction = 'Route Completed';
              String nextStopName = 'Destination';
              String distanceStr = '--';
              String nextStopDuration = '--';
              DriverStop? currentStop;

              try {
                currentStop = stops.firstWhere((s) => s.current);
              } catch (_) {
                try {
                  currentStop = stops.firstWhere((s) => !s.completed);
                } catch (_) {}
              }

              if (currentStop != null) {
                currentInstruction = 'Proceed to ${currentStop.name}';
                nextStopName = currentStop.name;
                distanceStr = currentStop.distance;
                nextStopDuration = '${currentStop.etaMinutes} min';
              }

              final boardingStop = stops.first;
              final destinationStop = stops.length >= 2 ? stops.last : null;

              // Build stop markers
              final markers = <Marker>[];
              if (userLocation != null) {
                markers.add(
                  Marker(
                    point: userLocation,
                    width: 48,
                    height: 48,
                    child: _UserLocationMarker(heading: userHeading),
                  ),
                );
              }
              for (final stop in stops) {
                if (stop.hasCoordinates) {
                  final pt = LatLng(stop.lat, stop.lon);
                  if (stop == boardingStop) {
                    markers.add(
                      Marker(
                        point: pt,
                        width: 36,
                        height: 36,
                        child: const _MapPin(icon: Icons.navigation, bg: green, color: Colors.white),
                      ),
                    );
                  } else if (stop == destinationStop) {
                    markers.add(
                      Marker(
                        point: pt,
                        width: 36,
                        height: 36,
                        child: const _MapPin(icon: Icons.location_on, bg: rose, color: Colors.white),
                      ),
                    );
                  } else {
                    markers.add(
                      Marker(
                        point: pt,
                        width: 24,
                        height: 24,
                        child: Center(child: _buildStopMarker(stop)),
                      ),
                    );
                  }
                }
              }

              final center = userLocation ?? (stops.isNotEmpty ? LatLng(stops.first.lat, stops.first.lon) : const LatLng(0, 0));

              if (_followUser && userLocation != null) {
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  _mapController.move(userLocation, _mapController.camera.zoom);
                });
              }

              return Stack(
                children: [
                  // 1. FlutterMap background
                  Positioned.fill(
                    child: FlutterMap(
                      mapController: _mapController,
                      options: MapOptions(
                        initialCenter: center,
                        initialZoom: 15,
                        interactionOptions: const InteractionOptions(
                          flags: InteractiveFlag.all,
                        ),
                        onPositionChanged: (pos, hasGesture) {
                          if (hasGesture) {
                            setState(() {
                              _followUser = false;
                            });
                          }
                        },
                      ),
                      children: [
                        TileLayer(
                          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                          userAgentPackageName: 'com.izee.driver',
                        ),
                        if (activeRoute.geometry.isNotEmpty)
                          PolylineLayer(
                            polylines: [
                              Polyline(
                                points: activeRoute.geometry,
                                color: green,
                                strokeWidth: 6,
                              ),
                            ],
                          ),
                        MarkerLayer(markers: markers),
                      ],
                    ),
                  ),

                  // 2. Floating Back Button
                  Positioned(
                    top: MediaQuery.of(context).padding.top + 10,
                    left: 16,
                    child: FloatingActionButton.small(
                      heroTag: 'exit_route_info',
                      backgroundColor: Colors.white,
                      foregroundColor: ink,
                      onPressed: () => Navigator.pop(context),
                      child: const Icon(Icons.close),
                    ),
                  ),

                  // 3. Floating Re-Center Button
                  Positioned(
                    bottom: 300,
                    right: 16,
                    child: FloatingActionButton.small(
                      heroTag: 'recenter_driver_nav',
                      backgroundColor: _followUser ? green : Colors.white,
                      foregroundColor: _followUser ? Colors.white : green,
                      onPressed: () {
                        setState(() {
                          _followUser = true;
                        });
                        if (userLocation != null) {
                          _mapController.move(userLocation, 16.0);
                        }
                      },
                      child: const Icon(Icons.my_location),
                    ),
                  ),

                  // 4. Top Route Info Card
                  Positioned(
                    top: MediaQuery.of(context).padding.top + 10,
                    left: 70,
                    right: 16,
                    child: Card(
                      elevation: 4,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      color: Colors.white,
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    activeRoute.routeName,
                                    style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 15, color: ink),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  const SizedBox(height: 2),
                                  Row(
                                    children: [
                                      Text(
                                        'Stop ${activeRoute.currentStopSequence} of ${activeRoute.totalStops}',
                                        style: const TextStyle(fontWeight: FontWeight.w700, color: green, fontSize: 13),
                                      ),
                                      const SizedBox(width: 8),
                                      const Icon(Icons.fiber_manual_record, size: 6, color: muted),
                                      const SizedBox(width: 8),
                                      Text(
                                        '${(activeRoute.progressPercent).toStringAsFixed(0)}% completed',
                                        style: const TextStyle(color: muted, fontSize: 13),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                            const Icon(Icons.directions_bus, color: green, size: 28),
                          ],
                        ),
                      ),
                    ),
                  ),

                  // 5. Bottom Navigation Control Card
                  Positioned(
                    bottom: MediaQuery.of(context).padding.bottom + 16,
                    left: 16,
                    right: 16,
                    child: Card(
                      elevation: 6,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      color: Colors.white,
                      child: Padding(
                        padding: const EdgeInsets.all(18),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            // Current Instruction
                            Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: green.withOpacity(0.12),
                                  ),
                                  child: const Icon(
                                    Icons.navigation,
                                    color: green,
                                    size: 24,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        'CURRENT INSTRUCTION',
                                        style: TextStyle(color: muted, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.6),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        currentInstruction,
                                        style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 18, color: ink),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                            const Divider(height: 24),

                            // Next stop details
                            Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        'NEXT STOP',
                                        style: TextStyle(color: muted, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.6),
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        nextStopName,
                                        style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15, color: ink),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ],
                                  ),
                                ),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    const Text(
                                      'DISTANCE',
                                      style: TextStyle(color: muted, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.6),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      distanceStr,
                                      style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16, color: green),
                                    ),
                                  ],
                                ),
                                const SizedBox(width: 18),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    const Text(
                                      'ETA',
                                      style: TextStyle(color: muted, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.6),
                                    ),
                                    const SizedBox(height: 2),
                                    Text(
                                      nextStopDuration,
                                      style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16, color: green),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                            const Divider(height: 24),

                            // Collapsible Stops List
                            InkWell(
                              onTap: () {
                                setState(() {
                                  _showStopsList = !_showStopsList;
                                });
                              },
                              child: Padding(
                                padding: const EdgeInsets.symmetric(vertical: 4),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      _showStopsList ? 'Hide Stops List' : 'Show Stops List',
                                      style: const TextStyle(fontWeight: FontWeight.w700, color: green, fontSize: 13),
                                    ),
                                    Icon(
                                      _showStopsList ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
                                      color: green,
                                      size: 20,
                                    ),
                                  ],
                                ),
                              ),
                            ),
                            if (_showStopsList) ...[
                              const SizedBox(height: 8),
                              Container(
                                constraints: const BoxConstraints(maxHeight: 150),
                                child: ListView.builder(
                                  shrinkWrap: true,
                                  physics: const ClampingScrollPhysics(),
                                  padding: EdgeInsets.zero,
                                  itemCount: stops.length,
                                  itemBuilder: (context, idx) {
                                    final stop = stops[idx];
                                    return Padding(
                                      padding: const EdgeInsets.symmetric(vertical: 6.0),
                                      child: Row(
                                        children: [
                                          Icon(
                                            stop.completed ? Icons.check_circle : stop.current ? Icons.radio_button_checked : Icons.radio_button_off,
                                            color: stop.completed || stop.current ? green : muted,
                                            size: 18,
                                          ),
                                          const SizedBox(width: 8),
                                          Expanded(
                                            child: Text(
                                              stop.name,
                                              style: TextStyle(
                                                color: stop.completed ? Colors.grey : ink,
                                                fontWeight: stop.current ? FontWeight.bold : FontWeight.normal,
                                                fontSize: 13,
                                              ),
                                            ),
                                          ),
                                          Text(
                                            stop.time,
                                            style: const TextStyle(color: muted, fontSize: 11),
                                          ),
                                        ],
                                      ),
                                    );
                                  },
                                ),
                              ),
                            ],
                            const SizedBox(height: 14),

                            // Action button
                            ElevatedButton(
                              onPressed: activeRoute.status == 'completed' || _advancing
                                  ? null
                                  : _advanceStop,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: green,
                                foregroundColor: Colors.white,
                                minimumSize: const Size.fromHeight(48),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  _advancing
                                      ? const SizedBox(
                                          width: 18,
                                          height: 18,
                                          child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            color: Colors.white,
                                          ),
                                        )
                                      : const Icon(Icons.check_circle_outline),
                                  const SizedBox(width: 8),
                                  Flexible(
                                    child: Text(
                                      activeRoute.status == 'completed'
                                          ? 'Route Completed'
                                          : 'Mark Next Stop Completed',
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              );
            },
          );
        },
      ),
    );
  }
}
// ──────────────────────────────────────────────────────────────────────────────
// TRIP SUMMARY SCREEN
// ──────────────────────────────────────────────────────────────────────────────

class TripSummaryScreen extends StatefulWidget {
  const TripSummaryScreen({
    super.key,
    required this.services,
    required this.routeInfo,
  });

  final DriverServices services;
  final DriverRouteInfo routeInfo;

  @override
  State<TripSummaryScreen> createState() => _TripSummaryScreenState();
}

class _TripSummaryScreenState extends State<TripSummaryScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _confettiCtrl;
  late final Animation<double> _heroScale;
  late final Animation<double> _heroFade;
  bool _ending = false;

  @override
  void initState() {
    super.initState();
    _confettiCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..forward();
    _heroScale = CurvedAnimation(
      parent: _confettiCtrl,
      curve: Curves.elasticOut,
    );
    _heroFade = CurvedAnimation(
      parent: _confettiCtrl,
      curve: const Interval(0, 0.6, curve: Curves.easeIn),
    );
  }

  @override
  void dispose() {
    _confettiCtrl.dispose();
    super.dispose();
  }

  String _elapsedLabel() {
    final started = widget.services.tripState.value.tripStartedAt;
    if (started != null) {
      final elapsed = DateTime.now().toUtc().difference(started);
      final h = elapsed.inHours;
      final m = elapsed.inMinutes.remainder(60);
      if (h > 0) return '${h}h ${m}m';
      return '${m}m';
    }
    // Fallback: compute from first-stop vs last-stop scheduled time strings
    // Handles formats like "6:00:00", "08:15 AM", "7:22:00"
    final stops = widget.routeInfo.stops;
    if (stops.isEmpty) return '--';
    final t0 = _parseStopTime(stops.first.time);
    final t1 = _parseStopTime(stops.last.time);
    if (t0 != null && t1 != null && t1.isAfter(t0)) {
      final diff = t1.difference(t0);
      final h = diff.inHours;
      final m = diff.inMinutes.remainder(60);
      if (h > 0) return '${h}h ${m}m';
      return '${m}m';
    }
    return '--';
  }

  /// Parses a stop time string into a DateTime using today's date.
  /// Handles 24-h formats like "6:00:00" / "14:30" and 12-h like "08:15 AM".
  DateTime? _parseStopTime(String raw) {
    try {
      final now = DateTime.now();
      String s = raw.trim();
      bool pm = false;
      if (s.toUpperCase().endsWith('PM')) {
        pm = true;
        s = s.substring(0, s.length - 2).trim();
      } else if (s.toUpperCase().endsWith('AM')) {
        s = s.substring(0, s.length - 2).trim();
      }
      final parts = s.split(':');
      int h = int.parse(parts[0]);
      final m = parts.length > 1 ? int.parse(parts[1]) : 0;
      if (pm && h != 12) h += 12;
      if (!pm && h == 12) h = 0;
      return DateTime(now.year, now.month, now.day, h, m);
    } catch (_) {
      return null;
    }
  }

  double _totalDistanceKm() {
    double total = 0;
    for (final stop in widget.routeInfo.stops) {
      if (stop.distanceKm > total) total = stop.distanceKm;
    }
    return total;
  }

  int _totalDurationMinutes() {
    int maxDuration = 0;
    for (final stop in widget.routeInfo.stops) {
      if (stop.etaMinutes > maxDuration) {
        maxDuration = stop.etaMinutes;
      }
    }
    return maxDuration;
  }

  Future<void> _endTrip(BuildContext ctx) async {
    if (_ending) return;
    setState(() => _ending = true);
    try {
      await widget.services.endTrip();
      if (!ctx.mounted) return;
      // Pop back all the way to the home screen.
      Navigator.of(ctx).popUntil((route) => route.isFirst);
    } catch (e) {
      if (!ctx.mounted) return;
      showAppPopup(
        ctx,
        message: e.toString().replaceFirst('Exception: ', ''),
        isSuccess: false,
      );
      setState(() => _ending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final routeInfo = widget.routeInfo;
    // When the route is marked complete, every stop is considered done
    // regardless of what the API returned for individual stop statuses.
    final allDone = routeInfo.isComplete;
    final completedCount =
        allDone ? routeInfo.stops.length : routeInfo.stops.where((s) => s.completed).length;
    final totalKm = _totalDistanceKm();
    final elapsedLabel = _elapsedLabel();
    final durationLabel = elapsedLabel == '0m' || elapsedLabel == '--'
        ? '${_totalDurationMinutes()} mins'
        : elapsedLabel;

    return Scaffold(
      body: Column(
        children: [
          // ── Animated hero header ──────────────────────────────────────────
          FadeTransition(
            opacity: _heroFade,
            child: Container(
              width: double.infinity,
              padding: EdgeInsets.fromLTRB(
                  20, MediaQuery.paddingOf(context).top + 28, 20, 28),
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF0F5F38), Color(0xFF18AB52)],
                ),
              ),
              child: Column(
                children: [
                  ScaleTransition(
                    scale: _heroScale,
                    child: Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.15),
                        shape: BoxShape.circle,
                        border: Border.all(
                            color: Colors.white.withOpacity(0.4), width: 2),
                      ),
                      child: const Icon(
                        Icons.check_circle_rounded,
                        color: Colors.white,
                        size: 48,
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'Route Completed!',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 26,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '${routeInfo.routeName}  •  ${routeInfo.origin} → ${routeInfo.destination}',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        color: Colors.white.withOpacity(0.8), fontSize: 13),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Distance: ${totalKm > 0 ? "${totalKm.toStringAsFixed(1)} km" : "--"}   •   Duration: $durationLabel',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ),

          // ── Scrollable body ───────────────────────────────────────────────
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(14, 20, 14, 28),
              children: [
                // Stats row
                Row(
                  children: [
                    _StatCard(
                      icon: Icons.pin_drop_outlined,
                      iconColor: const Color(0xFF12BD78),
                      label: 'Stops',
                      value: '$completedCount/${routeInfo.totalStops}',
                    ),
                    const SizedBox(width: 10),
                    _StatCard(
                      icon: Icons.straighten_outlined,
                      iconColor: const Color(0xFF2563EB),
                      label: 'Distance',
                      value: totalKm > 0
                          ? '${totalKm.toStringAsFixed(1)} km'
                          : '--',
                    ),
                    const SizedBox(width: 10),
                    _StatCard(
                      icon: Icons.timer_outlined,
                      iconColor: const Color(0xFFF59E0B),
                      label: 'Duration',
                      value: durationLabel,
                    ),
                  ],
                ),

                const SizedBox(height: 22),

                // Section title
                const Text(
                  'Stop Log',
                  style: TextStyle(
                    fontWeight: FontWeight.w900,
                    fontSize: 16,
                    color: Color(0xFF334155),
                  ),
                ),
                const SizedBox(height: 10),

                // Stop timeline
                ...routeInfo.stops.asMap().entries.map((entry) {
                  final idx = entry.key;
                  final stop = entry.value;
                  final isLast = idx == routeInfo.stops.length - 1;
                  return _SummaryStopRow(
                    stop: stop,
                    number: idx + 1,
                    isLast: isLast,
                    // Force every stop to show as completed when route is done.
                    forceComplete: allDone,
                  );
                }),

                const SizedBox(height: 24),

                // Performance card
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF0FDF4),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: const Color(0xFFBBF7D0)),
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: const BoxDecoration(
                          color: Color(0xFF12BD78),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.star_rounded,
                            color: Colors.white, size: 22),
                      ),
                      const SizedBox(width: 14),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Great job, Ahmed!',
                              style: TextStyle(
                                fontWeight: FontWeight.w900,
                                fontSize: 15,
                                color: Color(0xFF14532D),
                              ),
                            ),
                            SizedBox(height: 3),
                            Text(
                              'All stops completed on schedule.',
                              style: TextStyle(
                                  color: Color(0xFF166534), fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 28),

                // End Trip button
                FilledButton.icon(
                  onPressed: _ending ? null : () => _endTrip(context),
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF0F5F38),
                    minimumSize: const Size.fromHeight(54),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                  icon: _ending
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white),
                        )
                      : const Icon(Icons.flag_rounded),
                  label: Text(
                    _ending ? 'Ending Trip...' : 'End Trip & Return to Home',
                    style: const TextStyle(
                        fontWeight: FontWeight.w900, fontSize: 15),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// A compact stat card used in the summary hero row.
class _StatCard extends StatelessWidget {
  const _StatCard({
    required this.icon,
    required this.iconColor,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final Color iconColor;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFFE2E8F0)),
          boxShadow: const [
            BoxShadow(
                color: Color(0x0F000000),
                blurRadius: 10,
                offset: Offset(0, 3))
          ],
        ),
        child: Column(
          children: [
            CircleAvatar(
              radius: 18,
              backgroundColor: iconColor.withOpacity(0.12),
              child: Icon(icon, color: iconColor, size: 18),
            ),
            const SizedBox(height: 10),
            Text(
              value,
              style: const TextStyle(
                fontWeight: FontWeight.w900,
                fontSize: 17,
                color: Color(0xFF1E293B),
              ),
            ),
            const SizedBox(height: 3),
            Text(label,
                style: const TextStyle(color: muted, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}

/// A single row in the stop completion log.
class _SummaryStopRow extends StatelessWidget {
  const _SummaryStopRow({
    required this.stop,
    required this.number,
    required this.isLast,
    this.forceComplete = false,
  });

  final DriverStop stop;
  final int number;
  final bool isLast;
  /// When true, renders this stop as completed regardless of [stop.completed].
  final bool forceComplete;

  @override
  Widget build(BuildContext context) {
    final isDone = stop.completed || forceComplete;
    const lineColor = Color(0xFF12BD78);
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Timeline indicator
          Column(
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: const BoxDecoration(
                  color: lineColor,
                  shape: BoxShape.circle,
                ),
                child: isDone
                    ? const Icon(Icons.check, color: Colors.white, size: 16)
                    : Center(
                        child: Text(
                          '$number',
                          style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                              fontSize: 12),
                        ),
                      ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: lineColor.withOpacity(0.3),
                    margin: const EdgeInsets.symmetric(vertical: 3),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 14),
          // Stop info
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    stop.name,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 14,
                      color: Color(0xFF1E293B),
                    ),
                  ),
                  const SizedBox(height: 3),
                  Row(
                    children: [
                      const Icon(Icons.access_time, size: 13, color: muted),
                      const SizedBox(width: 4),
                      Text(stop.time,
                          style: const TextStyle(color: muted, fontSize: 12)),
                      const SizedBox(width: 10),
                      const Icon(Icons.straighten, size: 13, color: muted),
                      const SizedBox(width: 4),
                      Text(stop.distance,
                          style: const TextStyle(color: muted, fontSize: 12)),
                      const SizedBox(width: 10),
                      const Icon(Icons.timer_outlined, size: 13, color: muted),
                      const SizedBox(width: 4),
                      Text('${stop.etaMinutes} mins',
                          style: const TextStyle(color: muted, fontSize: 12)),
                    ],
                  ),
                ],
              ),
            ),
          ),
          // Completed badge
          Padding(
            padding: const EdgeInsets.only(top: 3),
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: isDone
                    ? const Color(0xFFD1FAE5)
                    : const Color(0xFFFEF9C3),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                isDone ? '✓ Done' : 'Missed',
                style: TextStyle(
                  color: isDone
                      ? const Color(0xFF065F46)
                      : const Color(0xFF92400E),
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ReportIssueScreen extends StatefulWidget {
  const ReportIssueScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<ReportIssueScreen> createState() => _ReportIssueScreenState();
}

class _ReportIssueScreenState extends State<ReportIssueScreen> {
  final _detailsController = TextEditingController();
  String selected = '';
  bool _submitting = false;
  String? _error;

  final incidents = const [
    IncidentChoice('Traffic Delay', Icons.traffic),
    IncidentChoice('Vehicle Breakdown', Icons.build_outlined),
    IncidentChoice('Heavy Traffic', Icons.directions_car),
    IncidentChoice('Route Deviation', Icons.alt_route),
    IncidentChoice('Accident/Emergency', Icons.emergency_outlined),
    IncidentChoice('Passenger Issue', Icons.groups),
  ];

  /// Critical issues go to the Control Center; others go to the Supervisor.
  static const _criticalCategories = {
    'Accident/Emergency',
    'Vehicle Breakdown',
  };

  bool get _isCritical => _criticalCategories.contains(selected);

  String get _recipient => 'Supervisor';

  Color get _sendColor =>
      _isCritical ? const Color(0xFFDC2626) : const Color(0xFFF59E0B);

  @override
  void dispose() {
    _detailsController.dispose();
    super.dispose();
  }

  Future<void> _submitReport() async {
    if (selected.isEmpty || _submitting) return;

    setState(() {
      _submitting = true;
      _error = null;
    });

    try {
      final response = await widget.services.submitIncidentReport(
        category: selected,
        details: _detailsController.text,
        recipient: _recipient,
      );
      if (!mounted) return;
      final incident = response['incident'] as Map<String, dynamic>?;
      final incidentId = incident?['incident_id']?.toString() ?? 'submitted';
      showAppPopup(
        context,
        message: 'Report sent to $_recipient: $incidentId',
        isSuccess: true,
      );
      Navigator.pop(context);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          OrangeTopBar(
              title: 'Report Issue', onBack: () => Navigator.pop(context)),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(12),
              children: [
                const WarningBand(),
                const SizedBox(height: 18),
                const Text(
                  'Select Incident Type',
                  style: TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 16,
                      color: Color(0xFF334155)),
                ),
                const SizedBox(height: 12),
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: incidents.length,
                  gridDelegate:
                      const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                    childAspectRatio: 1.32,
                  ),
                  itemBuilder: (context, index) {
                    final item = incidents[index];
                    final isCritItem =
                        _criticalCategories.contains(item.title);
                    return IncidentTile(
                      title: item.title,
                      icon: item.icon,
                      selected: selected == item.title,
                      isCritical: isCritItem,
                      onTap: () => setState(() => selected = item.title),
                    );
                  },
                ),

                // Routing destination indicator (appears once a type is chosen)
                if (selected.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 250),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: _isCritical
                          ? const Color(0xFFFEE2E2)
                          : const Color(0xFFFFF3CD),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                          color: _isCritical
                              ? const Color(0xFFFCA5A5)
                              : const Color(0xFFFDE68A)),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          _isCritical
                              ? Icons.local_police_outlined
                              : Icons.supervisor_account_outlined,
                          color: _isCritical
                              ? const Color(0xFFDC2626)
                              : const Color(0xFFF59E0B),
                          size: 20,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: RichText(
                            text: TextSpan(
                              style: const TextStyle(
                                  fontSize: 13,
                                  color: Color(0xFF334155)),
                              children: [
                                const TextSpan(text: 'Sends to: '),
                                TextSpan(
                                  text: _recipient,
                                  style: TextStyle(
                                    fontWeight: FontWeight.w900,
                                    color: _isCritical
                                        ? const Color(0xFFDC2626)
                                        : const Color(0xFFF59E0B),
                                  ),
                                ),
                                if (_isCritical)
                                  const TextSpan(
                                      text:
                                          ' — emergency protocol activated'),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 20),
                const Text(
                  'Additional Details (Optional)',
                  style: TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 16,
                      color: Color(0xFF334155)),
                ),
                const SizedBox(height: 10),
                CardShell(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      TextField(
                        controller: _detailsController,
                        minLines: 5,
                        maxLines: 5,
                        decoration: InputDecoration(
                          hintText: 'Describe the situation briefly...',
                          filled: true,
                          fillColor: const Color(0xFFFAFBFC),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                            borderSide:
                                const BorderSide(color: Color(0xFFE2E8F0)),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Keep your description brief and focus on driving safely',
                        style: TextStyle(color: muted, fontSize: 12),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                ValueListenableBuilder<DriverTripState>(
                  valueListenable: widget.services.tripState,
                  builder: (context, state, _) =>
                      ReportIncludesCard(state: state),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!,
                      style: const TextStyle(
                          color: danger, fontWeight: FontWeight.w700)),
                ],
                const SizedBox(height: 14),
                FilledButton.icon(
                  onPressed:
                      selected.isEmpty || _submitting ? null : _submitReport,
                  style: FilledButton.styleFrom(
                    minimumSize: const Size.fromHeight(54),
                    backgroundColor: selected.isEmpty ? orange : _sendColor,
                  ),
                  icon: _submitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(
                              strokeWidth: 2, color: Colors.white),
                        )
                      : Icon(_isCritical
                          ? Icons.emergency_share
                          : Icons.send),
                  label: Text(_submitting
                      ? 'Sending...'
                      : selected.isEmpty
                          ? 'Send Report'
                          : 'Send to $_recipient'),
                ),
                const SizedBox(height: 18),
                const Center(
                  child: Text(
                    'In case of emergency, call dispatch: 193XX',
                    style: TextStyle(color: muted),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  List<MessageData> _messages = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadMessages();
  }

  Future<void> _loadMessages() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final rows = await widget.services.loadMessages();
      if (!mounted) return;
      setState(() {
        _messages = rows.map(MessageData.fromApi).toList(growable: false);
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.toString().replaceFirst('Exception: ', '');
        _messages = widget.services
            .getCachedMessages()
            .map(MessageData.fromApi)
            .toList(growable: false);
        _loading = false;
      });
    }
  }

  Future<void> _markRead(MessageData message) async {
    if (message.id.isEmpty) return;
    await widget.services.markMessageRead(message.id);
    await _loadMessages();
  }

  @override
  Widget build(BuildContext context) {
    final unreadCount = _messages.where((message) => message.unread).length;

    return Scaffold(
      body: Column(
        children: [
          PurpleTopBar(title: 'Messages', onBack: () => Navigator.pop(context)),
          Container(
            width: double.infinity,
            margin: const EdgeInsets.all(12),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: purple.withOpacity(.82),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                const Icon(Icons.chat_bubble_outline, color: Colors.white),
                const SizedBox(width: 10),
                const Expanded(
                  child: Text(
                    'Supervisor and Control Center Communications',
                    style: TextStyle(
                        color: Colors.white, fontWeight: FontWeight.w800),
                  ),
                ),
                BadgePill(
                    label: '$unreadCount new', color: Colors.red, solid: true),
              ],
            ),
          ),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
              child: Text(_error!,
                  style: const TextStyle(
                      color: danger, fontWeight: FontWeight.w700)),
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _loadMessages,
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _messages.isEmpty
                      ? ListView(
                          padding: const EdgeInsets.all(24),
                          children: const [
                            SizedBox(height: 120),
                            Icon(Icons.mark_chat_read_outlined,
                                color: muted, size: 42),
                            SizedBox(height: 12),
                            Center(
                                child: Text('No messages yet',
                                    style: TextStyle(color: muted))),
                          ],
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                          itemCount: _messages.length,
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: 12),
                          itemBuilder: (context, index) => MessageCard(
                            data: _messages[index],
                            onMarkRead: () => _markRead(_messages[index]),
                          ),
                        ),
            ),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () async {
                        await widget.services.markAllAsRead();
                        await _loadMessages();
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: purple,
                        side: const BorderSide(color: purple),
                        minimumSize: const Size.fromHeight(48),
                      ),
                      icon: const Icon(Icons.done_all),
                      label: const Text('Mark All Read'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: _loadMessages,
                      style: FilledButton.styleFrom(
                        backgroundColor: purple,
                        minimumSize: const Size.fromHeight(48),
                      ),
                      icon: const Icon(Icons.refresh),
                      label: const Text('Refresh Messages'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class CardShell extends StatelessWidget {
  const CardShell({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.borderColor,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? borderColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: borderColor ?? const Color(0xFFE2E8F0),
          width: borderColor == null ? 1 : 2,
        ),
        boxShadow: const [
          BoxShadow(
              color: Color(0x14000000), blurRadius: 12, offset: Offset(0, 4)),
        ],
      ),
      child: child,
    );
  }
}

class GreenTopBar extends StatelessWidget {
  const GreenTopBar({
    super.key,
    required this.title,
    required this.onBack,
    this.actions,
  });

  final String title;
  final VoidCallback onBack;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context) {
    return ColoredTopBar(
      title: title,
      onBack: onBack,
      color: darkGreen,
      height: 76,
      actions: actions,
    );
  }
}

class PlainTopBar extends StatelessWidget {
  const PlainTopBar({super.key, required this.title, required this.onBack});

  final String title;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: SizedBox(
        height: 50,
        child: Row(
          children: [
            IconButton(onPressed: onBack, icon: const Icon(Icons.arrow_back)),
            Expanded(
              child: Text(
                title,
                textAlign: TextAlign.center,
                style:
                    const TextStyle(fontWeight: FontWeight.w900, fontSize: 18),
              ),
            ),
            const SizedBox(width: 48),
          ],
        ),
      ),
    );
  }
}

class OrangeTopBar extends StatelessWidget {
  const OrangeTopBar({super.key, required this.title, required this.onBack});

  final String title;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return ColoredTopBar(title: title, onBack: onBack, color: orange);
  }
}

class PurpleTopBar extends StatelessWidget {
  const PurpleTopBar({super.key, required this.title, required this.onBack});

  final String title;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return ColoredTopBar(title: title, onBack: onBack, color: purple);
  }
}

class ColoredTopBar extends StatelessWidget {
  const ColoredTopBar({
    super.key,
    required this.title,
    required this.onBack,
    required this.color,
    this.height = 56,
    this.actions,
  });

  final String title;
  final VoidCallback onBack;
  final Color color;
  final double height;
  final List<Widget>? actions;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: color,
      child: SafeArea(
        bottom: false,
        child: SizedBox(
          height: height,
          child: Row(
            children: [
              IconButton(
                onPressed: onBack,
                icon: const Icon(Icons.arrow_back, color: Colors.white),
              ),
              Expanded(
                child: Text(
                  title,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w900,
                    fontSize: 18,
                  ),
                ),
              ),
              if (actions != null)
                ...actions!
              else
                const SizedBox(width: 48),
            ],
          ),
        ),
      ),
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFFDFFBEA),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.check_circle_outline, color: green, size: 13),
          const SizedBox(width: 4),
          Text(
            label,
            style: const TextStyle(
              color: Color(0xFF009846),
              fontWeight: FontWeight.w800,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class RatingPill extends StatelessWidget {
  const RatingPill({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF3CD),
        borderRadius: BorderRadius.circular(14),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.star, color: Color(0xFFF59E0B), size: 13),
          SizedBox(width: 4),
          Text(
            '4.8 Rating',
            style: TextStyle(
              color: Color(0xFF92400E),
              fontWeight: FontWeight.w800,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.title, {super.key});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 18, bottom: 8),
      child: Text(
        title,
        style: const TextStyle(
          color: Color(0xFF475569),
          fontWeight: FontWeight.w900,
          fontSize: 16,
        ),
      ),
    );
  }
}

class SettingRow extends StatelessWidget {
  const SettingRow({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Icon(icon, color: muted),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(color: muted, fontSize: 12)),
                Text(subtitle,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ToggleRow extends StatelessWidget {
  const ToggleRow({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        children: [
          CircleAvatar(
              backgroundColor: paleGreen, child: Icon(icon, color: green)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                Text(subtitle, style: const TextStyle(color: muted)),
              ],
            ),
          ),
          Switch(value: true, onChanged: (_) {}, activeColor: green),
        ],
      ),
    );
  }
}

class MonthStats extends StatelessWidget {
  const MonthStats({super.key});

  @override
  Widget build(BuildContext context) {
    return const CardShell(
      child: Row(
        children: [
          Expanded(child: StatBlock(value: '42', label: 'Trips', color: green)),
          Expanded(
              child: StatBlock(
                  value: '156', label: 'Hours', color: Color(0xFF2563EB))),
          Expanded(
              child: StatBlock(value: '2,340', label: 'KM', color: purple)),
        ],
      ),
    );
  }
}

class StatBlock extends StatelessWidget {
  const StatBlock({
    super.key,
    required this.value,
    required this.label,
    required this.color,
  });

  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
              color: color, fontSize: 18, fontWeight: FontWeight.w900),
        ),
        Text(label, style: const TextStyle(color: muted)),
      ],
    );
  }
}

class OutlineAction extends StatelessWidget {
  const OutlineAction({
    super.key,
    required this.icon,
    required this.label,
    this.red = false,
    this.onPressed,
  });

  final IconData icon;
  final String label;
  final bool red;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onPressed ?? () {},
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(48),
        foregroundColor: red ? danger : ink,
        side: BorderSide(
            color: red ? const Color(0xFFFFB4B4) : const Color(0xFFE2E8F0)),
      ),
      icon: Icon(icon, size: 18),
      label: Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
    );
  }
}

class MapStatusCard extends StatelessWidget {
  const MapStatusCard({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    this.toggle = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool toggle;

  @override
  Widget build(BuildContext context) {
    return CardShell(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Row(
        children: [
          CircleAvatar(
            backgroundColor: paleGreen,
            child: Icon(icon, color: toggle ? green : const Color(0xFF2563EB)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                Text(subtitle,
                    style: const TextStyle(color: muted, fontSize: 12)),
              ],
            ),
          ),
          if (toggle)
            Switch(value: true, onChanged: (_) {}, activeColor: green),
        ],
      ),
    );
  }
}

class MapZoomButtons extends StatelessWidget {
  const MapZoomButtons({
    super.key,
    required this.onZoomIn,
    required this.onZoomOut,
  });

  final VoidCallback onZoomIn;
  final VoidCallback onZoomOut;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        FloatingActionButton.small(
          heroTag: 'plus',
          onPressed: onZoomIn,
          backgroundColor: Colors.white,
          foregroundColor: ink,
          child: const Icon(Icons.add),
        ),
        const SizedBox(height: 8),
        FloatingActionButton.small(
          heroTag: 'minus',
          onPressed: onZoomOut,
          backgroundColor: Colors.white,
          foregroundColor: ink,
          child: const Icon(Icons.remove),
        ),
      ],
    );
  }
}

class CurrentLocationPanel extends StatelessWidget {
  const CurrentLocationPanel({super.key, required this.services});

  final DriverServices services;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<DriverTripState>(
      valueListenable: services.tripState,
      builder: (context, state, _) {
        final position = state.lastPosition;
        return CardShell(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Expanded(
                    child: Text('Current Location',
                        style: TextStyle(color: muted)),
                  ),
                  StatusPill(label: state.active ? 'GPS Sending' : 'GPS Ready'),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                position == null ? 'Waiting for GPS' : 'Live driver location',
                style:
                    const TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 18),
              Text(
                position == null
                    ? 'Press Start Trip to send location'
                    : 'Lat: ${position.latitude.toStringAsFixed(5)}     Long: ${position.longitude.toStringAsFixed(5)}     Updated: ${state.lastSentAt == null ? 'pending' : 'Just now'}',
                style: const TextStyle(color: muted, fontSize: 12),
              ),
            ],
          ),
        );
      },
    );
  }
}

class GreenRouteHeader extends StatelessWidget {
  const GreenRouteHeader({
    super.key,
    required this.onBack,
    this.route,
    this.loading = false,
  });

  final VoidCallback onBack;
  final DriverRouteInfo? route;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    final currentStop = route?.currentStopSequence ?? 0;
    final totalStops = route?.totalStops ?? 0;
    final progress = route?.progressPercent ?? 0;
    final routeName = route?.routeName ?? 'no routes active';
    final routeDirection = route == null
        ? 'no routes active'
        : '${route!.origin} -> ${route!.destination}';

    return Container(
      color: darkGreen,
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(4, 0, 12, 18),
          child: Column(
            children: [
              Row(
                children: [
                  IconButton(
                    onPressed: onBack,
                    icon: const Icon(Icons.arrow_back, color: Colors.white),
                  ),
                  const Expanded(
                    child: Text(
                      'Route Information',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.w900),
                    ),
                  ),
                  const SizedBox(width: 48),
                ],
              ),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(.12),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white24),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Expanded(
                            child: Text('Current Route',
                                style: TextStyle(color: Colors.white70))),
                        Text('$currentStop',
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 28,
                                fontWeight: FontWeight.w900)),
                        Text(' of $totalStops',
                            style: const TextStyle(color: Colors.white)),
                      ],
                    ),
                    Text(
                      routeName,
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 22,
                          fontWeight: FontWeight.w900),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(routeDirection,
                        style: const TextStyle(color: Colors.white),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis),
                    const SizedBox(height: 22),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: loading
                            ? null
                            : progress.clamp(0, 100).toDouble() / 100,
                        minHeight: 7,
                        color: Colors.white,
                        backgroundColor: Colors.white24,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text('${progress.toStringAsFixed(0)}% Complete',
                        style: const TextStyle(color: Colors.white)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class DriverStop {
  const DriverStop({
    required this.name,
    required this.time,
    required this.badge,
    required this.completed,
    required this.current,
    required this.distance,
    required this.etaMinutes,
    required this.lat,
    required this.lon,
    required this.distanceKm,
  });

  factory DriverStop.fromApi(Map<String, dynamic> json) {
    final status = json['status']?.toString().toLowerCase() ?? 'upcoming';
    final distanceKm = _asDouble(json['distance_km']);
    final etaVal = json['eta_minutes'];

    String formattedDistance;
    if (distanceKm <= 0) {
      formattedDistance = '0 m';
    } else if (distanceKm < 1.0) {
      formattedDistance = '${(distanceKm * 1000).toStringAsFixed(0)} m';
    } else {
      formattedDistance = '${distanceKm.toStringAsFixed(1)} km';
    }

    return DriverStop(
      name: json['name']?.toString() ?? 'Unnamed stop',
      time: json['scheduled_time']?.toString() ?? '--',
      badge: status == 'completed'
          ? 'Completed'
          : status == 'next'
              ? 'Next Stop'
              : '',
      completed: status == 'completed',
      current: status == 'next',
      distance: formattedDistance,
      etaMinutes: etaVal != null ? _asInt(etaVal) : (status == 'next' ? 5 : 0),
      lat: _asDouble(json['lat']),
      lon: _asDouble(json['lon']),
      distanceKm: distanceKm,
    );
  }

  final String name;
  final String time;
  final String badge;
  final bool completed;
  final bool current;
  final String distance;
  final int etaMinutes;
  final double lat;
  final double lon;
  final double distanceKm;

  bool get hasCoordinates => lat != 0 && lon != 0;
}

class DriverRouteInfo {
  const DriverRouteInfo({
    required this.routeName,
    required this.origin,
    required this.destination,
    required this.currentStopSequence,
    required this.totalStops,
    required this.progressPercent,
    required this.status,
    required this.stops,
    required this.geometry,
  });

  factory DriverRouteInfo.fromApi(Map<String, dynamic> json) {
    final stopsJson = json['stops'];
    final stops = stopsJson is List
        ? stopsJson
            .whereType<Map<String, dynamic>>()
            .map(DriverStop.fromApi)
            .toList(growable: false)
        : const <DriverStop>[];
    final geometryJson = json['geometry'];
    final geometry = geometryJson is List
        ? geometryJson
            .whereType<Map<String, dynamic>>()
            .map((point) => LatLng(
                  _asDouble(point['lat']),
                  _asDouble(point['lon']),
                ))
            .where((point) => point.latitude != 0 && point.longitude != 0)
            .toList(growable: false)
        : const <LatLng>[];

    return DriverRouteInfo(
      routeName: json['route_name']?.toString() ??
          json['route_id']?.toString() ??
          'Assigned Route',
      origin: _nonEmptyText(json['origin'], 'Origin not available'),
      destination:
          _nonEmptyText(json['destination'], 'Destination not available'),
      currentStopSequence: _asInt(json['current_stop_sequence']),
      totalStops: _asInt(json['total_stops']) == 0
          ? stops.length
          : _asInt(json['total_stops']),
      progressPercent: _asDouble(json['progress_percent']),
      status: json['status']?.toString() ?? 'active',
      stops: stops,
      geometry: geometry,
    );
  }

  final String routeName;
  final String origin;
  final String destination;
  final int currentStopSequence;
  final int totalStops;
  final double progressPercent;
  final String status;
  final List<DriverStop> stops;
  final List<LatLng> geometry;

  bool get isComplete =>
      status.toLowerCase() == 'completed' || progressPercent >= 100;

  bool get hasRoutePath =>
      geometry.length >= 2 || stops.where((stop) => stop.hasCoordinates).length >= 2;
}

String _nonEmptyText(Object? value, String fallback) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? fallback : text;
}

int _asInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

double _asDouble(Object? value) {
  if (value is double) return value;
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}

class StopTimelineCard extends StatelessWidget {
  const StopTimelineCard({super.key, required this.stop, required this.number});

  final DriverStop stop;
  final int number;

  @override
  Widget build(BuildContext context) {
    final lineColor =
        stop.completed || stop.current ? green : const Color(0xFFCBD5E1);
    return CardShell(
      borderColor: stop.current ? green : null,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            backgroundColor:
                stop.completed || stop.current ? green : Colors.white,
            foregroundColor:
                stop.completed || stop.current ? Colors.white : muted,
            child: stop.completed
                ? const Icon(Icons.check, size: 18)
                : Text('$number'),
          ),
          Container(
            width: 1,
            height: 70,
            margin: const EdgeInsets.symmetric(horizontal: 12),
            color: lineColor,
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(stop.name,
                          style: const TextStyle(
                              fontSize: 16, fontWeight: FontWeight.w800)),
                    ),
                    if (stop.badge.isNotEmpty)
                      BadgePill(
                          label: stop.badge,
                          color:
                              stop.current ? green : const Color(0xFF22C55E)),
                  ],
                ),
                const SizedBox(height: 7),
                Row(
                  children: [
                    const Icon(Icons.access_time, size: 16, color: muted),
                    const SizedBox(width: 5),
                    Text(stop.time, style: const TextStyle(color: muted)),
                  ],
                ),
                if (!stop.completed) ...[
                  const SizedBox(height: 7),
                  Wrap(
                    spacing: 12,
                    children: [
                      Text(
                        'ETA: ${stop.etaMinutes} mins',
                        style: const TextStyle(
                            color: Color(0xFF2563EB),
                            fontWeight: FontWeight.w700),
                      ),
                      Text(stop.distance, style: const TextStyle(color: muted)),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class WarningBand extends StatelessWidget {
  const WarningBand({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: orange.withOpacity(.9),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const Row(
        children: [
          Icon(Icons.warning_amber_rounded, color: Colors.white),
          SizedBox(width: 8),
          Expanded(
            child: Text(
              'Report incidents quickly and safely',
              style:
                  TextStyle(color: Colors.white, fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
  }
}

class IncidentChoice {
  const IncidentChoice(this.title, this.icon);

  final String title;
  final IconData icon;
}

class IncidentTile extends StatelessWidget {
  const IncidentTile({
    super.key,
    required this.title,
    required this.icon,
    required this.selected,
    required this.onTap,
    this.isCritical = false,
  });

  final String title;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;
  /// When true, the tile is styled with red accents to signal emergency routing.
  final bool isCritical;

  @override
  Widget build(BuildContext context) {
    final activeColor = isCritical ? const Color(0xFFDC2626) : green;
    final selectedBg =
        isCritical ? const Color(0xFFFEF2F2) : const Color(0xFFEFF6FF);
    final selectedBorder =
        isCritical ? const Color(0xFFFCA5A5) : const Color(0xFFBFDBFE);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        decoration: BoxDecoration(
          color: selected ? selectedBg : Colors.white,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
              color: selected ? selectedBorder : Colors.white),
          boxShadow: const [
            BoxShadow(color: Color(0x0F000000), blurRadius: 10)
          ],
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon,
                color: selected
                    ? activeColor
                    : isCritical
                        ? const Color(0xFFDC2626)
                        : orange,
                size: 30),
            const SizedBox(height: 12),
            Text(title,
                textAlign: TextAlign.center,
                style: const TextStyle(fontWeight: FontWeight.w800)),
            if (selected) ...[
              const SizedBox(height: 8),
              CircleAvatar(
                radius: 10,
                backgroundColor: activeColor,
                child:
                    const Icon(Icons.check, color: Colors.white, size: 14),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class ReportIncludesCard extends StatelessWidget {
  const ReportIncludesCard({super.key, required this.state});

  final DriverTripState state;

  @override
  Widget build(BuildContext context) {
    final position = state.lastPosition;
    final locationText = position == null
        ? 'Will use current GPS when submitted'
        : '${position.latitude.toStringAsFixed(5)}, ${position.longitude.toStringAsFixed(5)}';
    final timeText = DateTime.now().toLocal().toString().split('.').first;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFEFF6FF),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFBFDBFE)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Report will include:', style: TextStyle(color: muted)),
          const SizedBox(height: 16),
          Text('Current Location: $locationText'),
          const SizedBox(height: 6),
          Text('Time: $timeText'),
          const SizedBox(height: 6),
          Text('Vehicle: ${state.vehicleId}'),
          const SizedBox(height: 6),
          Text('Route: ${state.routeId}'),
        ],
      ),
    );
  }
}

class BadgePill extends StatelessWidget {
  const BadgePill({
    super.key,
    required this.label,
    this.color = green,
    this.solid = false,
  });

  final String label;
  final Color color;
  final bool solid;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: solid ? color : color.withOpacity(.14),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: solid ? Colors.white : color,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class MessageData {
  const MessageData(
      this.source, this.title, this.body, this.time, this.unread, this.tag,
      {this.id = ''});

  factory MessageData.fromApi(Map<String, dynamic> data) {
    final priority = (data['priority'] ?? '').toString();
    return MessageData(
      (data['sender'] ?? 'Control Center').toString(),
      (data['subject'] ?? 'Control Center Message').toString(),
      (data['body'] ?? '').toString(),
      _messageTimeLabel(data['created_at']?.toString()),
      data['read'] != true,
      priority == 'urgent' ? 'Urgent' : '',
      id: (data['message_id'] ?? '').toString(),
    );
  }

  final String source;
  final String title;
  final String body;
  final String time;
  final bool unread;
  final String tag;
  final String id;
}

class MessageCard extends StatelessWidget {
  const MessageCard({super.key, required this.data, this.onMarkRead});

  final MessageData data;
  final VoidCallback? onMarkRead;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border(
            left: BorderSide(
                color: data.unread ? purple : Colors.transparent, width: 4)),
        boxShadow: const [
          BoxShadow(
              color: Color(0x14000000), blurRadius: 10, offset: Offset(0, 3))
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(data.source, style: const TextStyle(color: muted)),
              if (data.tag.isNotEmpty) ...[
                const SizedBox(width: 8),
                const BadgePill(
                    label: 'Urgent', color: Colors.red, solid: true),
              ],
              const Spacer(),
              Icon(data.unread ? Icons.access_time : Icons.done_all,
                  color: data.unread ? muted : const Color(0xFF2563EB)),
            ],
          ),
          const SizedBox(height: 6),
          Text(data.title,
              style:
                  const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 22),
          Text(data.body,
              style: const TextStyle(color: Color(0xFF334155), height: 1.35)),
          const SizedBox(height: 20),
          Row(
            children: [
              Text(data.time,
                  style: const TextStyle(color: muted, fontSize: 12)),
              const Spacer(),
              if (data.unread)
                OutlinedButton(
                    onPressed: onMarkRead, child: const Text('Mark as Read')),
            ],
          ),
        ],
      ),
    );
  }
}

String _messageTimeLabel(String? value) {
  if (value == null || value.isEmpty) return 'Just now';
  final parsed = DateTime.tryParse(value);
  if (parsed == null) return value;
  final local = parsed.toLocal();
  final age = DateTime.now().difference(local);
  if (age.inMinutes < 1) return 'Just now';
  if (age.inMinutes < 60) return '${age.inMinutes} mins ago';
  if (age.inHours < 24) return '${age.inHours} hours ago';
  return '${local.year}-${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')}';
}

void showAppPopup(
  BuildContext context, {
  required String message,
  required bool isSuccess,
  String? title,
}) {
  showDialog(
    context: context,
    builder: (context) {
      final primaryColor = isSuccess ? green : danger;
      final icon = isSuccess ? Icons.check_circle_outline : Icons.error_outline;
      final defaultTitle = title ?? (isSuccess ? 'Success' : 'Error');

      return Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        elevation: 12,
        backgroundColor: Colors.white,
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: primaryColor.withOpacity(0.12),
                child: Icon(icon, color: primaryColor, size: 36),
              ),
              const SizedBox(height: 18),
              Text(
                defaultTitle,
                style: const TextStyle(
                  color: ink,
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                  fontFamily: 'Roboto',
                ),
              ),
              const SizedBox(height: 10),
              Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: muted,
                  fontSize: 14,
                  height: 1.4,
                  fontFamily: 'Roboto',
                ),
              ),
              const SizedBox(height: 22),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => Navigator.pop(context),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: primaryColor,
                    foregroundColor: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                  child: const Text(
                    'OK',
                    style: TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 15,
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    },
  );
}

const fallbackMessages = [
  MessageData(
    'Control Center',
    'Route Change Alert',
    'Due to roadwork on Main St, please use alternate route via Bridge Rd.',
    '10 mins ago',
    true,
    'Urgent',
  ),
  MessageData(
    'Dispatch',
    'Passenger Count Request',
    'Please confirm current passenger count at next stop.',
    '25 mins ago',
    true,
    '',
  ),
  MessageData(
    'Operations',
    'Weather Advisory',
    'Rain expected in 30 mins. Please drive with extra caution.',
    '1 hour ago',
    true,
    '',
  ),
];

class MyTripsScreen extends StatefulWidget {
  const MyTripsScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<MyTripsScreen> createState() => _MyTripsScreenState();
}

class _MyTripsScreenState extends State<MyTripsScreen> {
  late Future<List<Map<String, dynamic>>> _dutiesFuture;

  @override
  void initState() {
    super.initState();
    _dutiesFuture = widget.services.loadAssignedDuties();
  }

  void _refresh() {
    setState(() {
      _dutiesFuture = widget.services.loadAssignedDuties();
    });
  }

  String _plannedDurationLabel(String startTime, String endTime) {
    final minutes = _durationMinutes(startTime, endTime);
    if (minutes == null) return 'Duration: Not available';
    final hours = minutes ~/ 60;
    final mins = minutes % 60;
    return 'Duration: ${hours}h ${mins.toString().padLeft(2, '0')}m';
  }

  int? _durationMinutes(String startTime, String endTime) {
    int? parse(String value) {
      final clean = value.trim();
      if (clean.isEmpty) return null;
      final parts = clean.split(':');
      if (parts.length < 2) return null;
      final hour = int.tryParse(parts[0]);
      final minute = int.tryParse(parts[1]);
      if (hour == null || minute == null) return null;
      return hour * 60 + minute;
    }

    final start = parse(startTime);
    final end = parse(endTime);
    if (start == null || end == null) return null;
    final adjustedEnd = end < start ? end + 24 * 60 : end;
    final duration = adjustedEnd - start;
    return duration > 0 ? duration : null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          GreenTopBar(
            title: 'My Trips',
            onBack: () => Navigator.pop(context),
          ),
          Expanded(
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _dutiesFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(
                      child: CircularProgressIndicator(color: green));
                }
                if (snapshot.hasError) {
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline,
                              color: danger, size: 48),
                          const SizedBox(height: 12),
                          Text(
                            snapshot.error
                                .toString()
                                .replaceFirst('Exception: ', ''),
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: muted),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: _refresh,
                            child: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  );
                }

                final duties = snapshot.data ?? const [];
                if (duties.isEmpty) {
                  return Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.route_outlined,
                            color: muted, size: 48),
                        const SizedBox(height: 12),
                        const Text('no routes assigned',
                            style: TextStyle(color: muted)),
                        const SizedBox(height: 16),
                        ElevatedButton(
                          onPressed: _refresh,
                          child: const Text('Refresh'),
                        ),
                      ],
                    ),
                  );
                }

                return ValueListenableBuilder<DriverTripState>(
                  valueListenable: widget.services.tripState,
                  builder: (context, state, _) {
                    return ListView.separated(
                      padding: const EdgeInsets.all(12),
                      itemCount: duties.length,
                      separatorBuilder: (_, __) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final duty = duties[index];
                        final assignmentId = duty['assignment_id']?.toString() ?? '';
                        final routeId = duty['route_id']?.toString() ?? '';
                        final routeName = duty['route_name']?.toString() ?? routeId;
                        final tripId = duty['trip_id']?.toString() ?? '';
                        final vehicleId = duty['vehicle_id']?.toString() ?? '';
                        final origin = duty['origin']?.toString() ?? '';
                        final destination = duty['destination']?.toString() ?? '';
                        final startTime = duty['start_time']?.toString() ??
                            duty['planned_start_time']?.toString() ??
                            '';
                        final endTime = duty['end_time']?.toString() ??
                            duty['planned_end_time']?.toString() ??
                            '';
                        final serviceDate = duty['service_date']?.toString() ?? '';
                        final statusStr = (duty['status']?.toString() ?? 'scheduled').toLowerCase();

                        final isCurrentlyActiveTrip = state.active && state.assignmentId == assignmentId;

                        Color statusColor;
                        Color statusBg;
                        String statusLabel;
                        if (statusStr == 'active' || isCurrentlyActiveTrip) {
                          statusColor = darkGreen;
                          statusBg = green.withOpacity(0.12);
                          statusLabel = 'ACTIVE';
                        } else if (statusStr == 'completed') {
                          statusColor = purple;
                          statusBg = purple.withOpacity(0.12);
                          statusLabel = 'COMPLETED';
                        } else if (statusStr == 'cancelled') {
                          statusColor = danger;
                          statusBg = danger.withOpacity(0.12);
                          statusLabel = 'CANCELLED';
                        } else {
                          statusColor = muted;
                          statusBg = const Color(0xFFF1F5F9);
                          statusLabel = 'SCHEDULED';
                        }

                        return Container(
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: isCurrentlyActiveTrip ? green : const Color(0xFFE2E8F0),
                              width: isCurrentlyActiveTrip ? 2 : 1,
                            ),
                            boxShadow: const [
                              BoxShadow(
                                color: Color(0x0F000000),
                                blurRadius: 10,
                                offset: Offset(0, 3),
                              ),
                            ],
                          ),
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: Text(
                                      routeName,
                                      style: const TextStyle(
                                        fontSize: 18,
                                        fontWeight: FontWeight.w900,
                                        color: ink,
                                      ),
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                      vertical: 4,
                                    ),
                                    decoration: BoxDecoration(
                                      color: statusBg,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      statusLabel,
                                      style: TextStyle(
                                        color: statusColor,
                                        fontSize: 10,
                                        fontWeight: FontWeight.w900,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              if (tripId.isNotEmpty) ...[
                                Text(
                                  'Trip ID: $tripId',
                                  style: const TextStyle(color: muted, fontSize: 13),
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                const SizedBox(height: 4),
                              ],
                              if (serviceDate.isNotEmpty) ...[
                                Text(
                                  'Date: $serviceDate',
                                  style: const TextStyle(color: muted, fontSize: 13),
                                ),
                                const SizedBox(height: 4),
                              ],
                              if (vehicleId.isNotEmpty) ...[
                                Text(
                                  'Vehicle: $vehicleId',
                                  style: const TextStyle(color: muted, fontSize: 13),
                                ),
                                const SizedBox(height: 4),
                              ],
                              const SizedBox(height: 14),
                              Row(
                                children: [
                                  const Icon(Icons.circle, size: 10, color: green),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      origin.isNotEmpty
                                          ? origin
                                          : 'Origin not available',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w700,
                                        fontSize: 14,
                                      ),
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                              Container(
                                width: 2,
                                height: 16,
                                margin: const EdgeInsets.only(left: 4),
                                color: const Color(0xFFCBD5E1),
                              ),
                              Row(
                                children: [
                                  const Icon(Icons.place, size: 12, color: danger),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      destination.isNotEmpty
                                          ? destination
                                          : 'Destination not available',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w700,
                                        fontSize: 14,
                                      ),
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              Row(
                                children: [
                                  const Icon(Icons.access_time, size: 16, color: muted),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(
                                      '$startTime - $endTime',
                                      style: const TextStyle(color: muted, fontSize: 13),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Row(
                                children: [
                                  const Icon(Icons.timer_outlined,
                                      size: 16, color: muted),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(
                                      _plannedDurationLabel(
                                          startTime, endTime),
                                      style: const TextStyle(
                                          color: muted, fontSize: 13),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Row(
                                children: [
                                  const Spacer(),
                                  const SizedBox(width: 10),
                                  if (statusStr == 'scheduled')
                                    ElevatedButton(
                                      onPressed: () async {
                                        try {
                                          debugPrint(
                                              'SELECTED_ASSIGNMENT: $duty');
                                          await widget.services.startAssignment(
                                            assignmentId: assignmentId,
                                            routeId: routeId,
                                            tripId: tripId,
                                            vehicleId: vehicleId,
                                          );
                                          showAppPopup(
                                            context,
                                            message: 'Started assignment for $routeName',
                                            isSuccess: true,
                                          );
                                          if (context.mounted) {
                                            Navigator.pushReplacement(
                                              context,
                                              MaterialPageRoute(
                                                builder: (_) => LiveMapScreen(
                                                  services: widget.services,
                                                ),
                                              ),
                                            );
                                          }
                                        } catch (e) {
                                          showAppPopup(
                                            context,
                                            message: 'Failed to start trip: ${e.toString().replaceFirst('Exception: ', '')}',
                                            isSuccess: false,
                                          );
                                        }
                                      },
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor: green,
                                        foregroundColor: Colors.white,
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 14,
                                          vertical: 6,
                                        ),
                                        minimumSize: Size.zero,
                                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                      ),
                                      child: const Text(
                                        'Start Trip',
                                        style: TextStyle(
                                          fontWeight: FontWeight.w800,
                                          fontSize: 12,
                                        ),
                                      ),
                                    )
                                  else if (statusStr == 'active' || isCurrentlyActiveTrip)
                                    ElevatedButton(
                                      onPressed: () async {
                                        try {
                                          debugPrint(
                                              'SELECTED_ASSIGNMENT: $duty');
                                          await widget.services.startAssignment(
                                            assignmentId: assignmentId,
                                            routeId: routeId,
                                            tripId: tripId,
                                            vehicleId: vehicleId,
                                          );
                                          if (context.mounted) {
                                            Navigator.pushReplacement(
                                              context,
                                              MaterialPageRoute(
                                                builder: (_) => LiveMapScreen(
                                                  services: widget.services,
                                                ),
                                              ),
                                            );
                                          }
                                        } catch (e) {
                                          showAppPopup(
                                            context,
                                            message: 'Failed to continue trip: ${e.toString().replaceFirst('Exception: ', '')}',
                                            isSuccess: false,
                                          );
                                        }
                                      },
                                      style: ElevatedButton.styleFrom(
                                        backgroundColor: darkGreen,
                                        foregroundColor: Colors.white,
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 14,
                                          vertical: 6,
                                        ),
                                        minimumSize: Size.zero,
                                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                      ),
                                      child: const Text(
                                        'Continue Trip',
                                        style: TextStyle(
                                          fontWeight: FontWeight.w800,
                                          fontSize: 12,
                                        ),
                                      ),
                                    )
                                  else if (statusStr == 'completed')
                                    const Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(Icons.check_circle_outline, color: purple, size: 16),
                                        SizedBox(width: 4),
                                        Text(
                                          'Completed',
                                          style: TextStyle(
                                            color: purple,
                                            fontWeight: FontWeight.w700,
                                            fontSize: 12,
                                          ),
                                        ),
                                      ],
                                    ),
                                ],
                              ),
                            ],
                          ),
                        );
                      },
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class TripHistoryScreen extends StatefulWidget {
  const TripHistoryScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<TripHistoryScreen> createState() => _TripHistoryScreenState();
}

class _TripHistoryScreenState extends State<TripHistoryScreen> {
  late Future<List<Map<String, dynamic>>> _historyFuture;
  String _timeFilter = 'All'; // 'Today', 'This Week', 'All'
  String _statusFilter = 'All'; // 'Completed', 'Cancelled', 'All'

  @override
  void initState() {
    super.initState();
    _historyFuture = widget.services.loadTripHistory();
  }

  void _refresh() {
    setState(() {
      _historyFuture = widget.services.loadTripHistory();
    });
  }

  Future<void> _clearHistory() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear Trip History'),
        content: const Text('Are you sure you want to permanently clear all trip history? This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            style: TextButton.styleFrom(foregroundColor: danger),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Clear All'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      try {
        await widget.services.clearTripHistory();
        _refresh();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Trip history cleared successfully'),
              backgroundColor: darkGreen,
            ),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to clear trip history: $e'),
              backgroundColor: danger,
            ),
          );
        }
      }
    }
  }

  Widget _buildStatusBadge(String status) {
    Color badgeColor;
    Color textColor;
    String label = status.toUpperCase();

    switch (status.toLowerCase()) {
      case 'completed':
        badgeColor = const Color(0xFFE6F4EA);
        textColor = const Color(0xFF137333);
        break;
      case 'cancelled':
        badgeColor = const Color(0xFFFCE8E6);
        textColor = const Color(0xFFC5221F);
        break;
      case 'interrupted':
        badgeColor = const Color(0xFFFEF7E0);
        textColor = const Color(0xFFB06000);
        break;
      default:
        badgeColor = const Color(0xFFF1F5F9);
        textColor = const Color(0xFF475569);
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: badgeColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: textColor,
          fontSize: 10,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }

  String _formatTime(String? timeStr, String fallback) {
    if (timeStr == null || timeStr.isEmpty) return fallback;
    try {
      final dt = DateTime.parse(timeStr).toLocal();
      final hour = dt.hour;
      final minute = dt.minute;
      final period = hour >= 12 ? 'PM' : 'AM';
      final formattedHour = hour == 0 ? 12 : (hour > 12 ? hour - 12 : hour);
      final formattedMinute = minute.toString().padLeft(2, '0');
      return '$formattedHour:$formattedMinute $period';
    } catch (_) {
      return timeStr;
    }
  }

  String _formatDuration(
    String? actualStart,
    String? actualEnd,
    String plannedStart,
    String plannedEnd,
    String fallbackDuration,
  ) {
    if (fallbackDuration.isNotEmpty) return fallbackDuration;
    if (actualStart == null || actualStart.isEmpty || actualEnd == null || actualEnd.isEmpty) {
      return _formatPlannedDuration(plannedStart, plannedEnd);
    }
    try {
      final start = DateTime.parse(actualStart);
      final end = DateTime.parse(actualEnd);
      final diff = end.difference(start);
      final minutes = diff.inMinutes;
      if (minutes < 0) return _formatPlannedDuration(plannedStart, plannedEnd);
      if (minutes < 60) {
        return '${minutes}m';
      } else {
        final hours = minutes ~/ 60;
        final remainingMins = minutes % 60;
        return '${hours}h ${remainingMins}m';
      }
    } catch (_) {
      return _formatPlannedDuration(plannedStart, plannedEnd);
    }
  }

  String _formatPlannedDuration(String startTime, String endTime) {
    int? parse(String value) {
      final clean = value.trim();
      if (clean.isEmpty) return null;
      final parts = clean.split(':');
      if (parts.length < 2) return null;
      final hour = int.tryParse(parts[0]);
      final minute = int.tryParse(parts[1]);
      if (hour == null || minute == null) return null;
      return hour * 60 + minute;
    }

    final start = parse(startTime);
    final end = parse(endTime);
    if (start == null || end == null) return 'Not available';
    final adjustedEnd = end < start ? end + 24 * 60 : end;
    final minutes = adjustedEnd - start;
    if (minutes <= 0) return 'Not available';
    final hours = minutes ~/ 60;
    final mins = minutes % 60;
    return '${hours}h ${mins}m';
  }

  List<Map<String, dynamic>> _applyFilters(List<Map<String, dynamic>> trips) {
    final now = DateTime.now();
    final todayStr = now.toIso8601String().split('T')[0];

    return trips.where((trip) {
      // 1. Time Filter
      final serviceDate = trip['service_date']?.toString() ?? '';
      final completedAtStr = trip['completed_at']?.toString() ?? '';

      bool matchesTime = true;
      if (_timeFilter == 'Today') {
        matchesTime = serviceDate == todayStr || completedAtStr.startsWith(todayStr);
      } else if (_timeFilter == 'This Week') {
        try {
          final date = serviceDate.isNotEmpty
              ? DateTime.parse(serviceDate)
              : completedAtStr.isNotEmpty
                  ? DateTime.parse(completedAtStr)
                  : null;
          if (date != null) {
            final difference = now.difference(date).inDays;
            matchesTime = difference <= 7;
          }
        } catch (_) {
          matchesTime = true;
        }
      }

      // 2. Status Filter
      bool matchesStatus = true;
      final status = (trip['status']?.toString() ?? '').toLowerCase();
      if (_statusFilter == 'Completed') {
        matchesStatus = status == 'completed';
      } else if (_statusFilter == 'Cancelled') {
        matchesStatus = status == 'cancelled';
      }

      return matchesTime && matchesStatus;
    }).toList();
  }

  Widget _buildFilterChip(String label, bool isSelected, Function(String) onSelect) {
    return ChoiceChip(
      label: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          color: isSelected ? darkGreen : ink,
        ),
      ),
      selected: isSelected,
      onSelected: (_) => onSelect(label),
      selectedColor: green.withOpacity(0.15),
      checkmarkColor: darkGreen,
      backgroundColor: const Color(0xFFF1F5F9),
      padding: const EdgeInsets.symmetric(horizontal: 4),
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          GreenTopBar(
            title: 'Trip History',
            onBack: () => Navigator.pop(context),
            actions: [
              IconButton(
                icon: const Icon(Icons.delete_sweep, color: Colors.white),
                tooltip: 'Clear History',
                onPressed: _clearHistory,
              ),
            ],
          ),
          // Filter Bar
          Container(
            padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
            decoration: const BoxDecoration(
              color: Colors.white,
              border: Border(bottom: BorderSide(color: Color(0xFFE2E8F0))),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text('Time: ', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: ink)),
                    const SizedBox(width: 6),
                    _buildFilterChip('Today', _timeFilter == 'Today', (val) => setState(() => _timeFilter = val)),
                    const SizedBox(width: 6),
                    _buildFilterChip('This Week', _timeFilter == 'This Week', (val) => setState(() => _timeFilter = val)),
                    const SizedBox(width: 6),
                    _buildFilterChip('All', _timeFilter == 'All', (val) => setState(() => _timeFilter = val)),
                  ],
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    const Text('Status: ', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 12, color: ink)),
                    const SizedBox(width: 6),
                    _buildFilterChip('Completed', _statusFilter == 'Completed', (val) => setState(() => _statusFilter = val)),
                    const SizedBox(width: 6),
                    _buildFilterChip('Cancelled', _statusFilter == 'Cancelled', (val) => setState(() => _statusFilter = val)),
                    const SizedBox(width: 6),
                    _buildFilterChip('All', _statusFilter == 'All', (val) => setState(() => _statusFilter = val)),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _historyFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(
                    child: CircularProgressIndicator(color: green),
                  );
                }
                if (snapshot.hasError) {
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline, color: danger, size: 48),
                          const SizedBox(height: 12),
                          Text(
                            snapshot.error
                                .toString()
                                .replaceFirst('Exception: ', ''),
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: muted),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: _refresh,
                            child: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  );
                }

                final rawHistory = snapshot.data ?? const [];
                final history = _applyFilters(rawHistory);

                if (history.isEmpty) {
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.history_outlined, size: 64, color: muted),
                          const SizedBox(height: 16),
                          const Text(
                            'No matching completed trips yet.',
                            style: TextStyle(
                              fontSize: 16,
                              color: muted,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: _refresh,
                            child: const Text('Refresh'),
                          ),
                        ],
                      ),
                    ),
                  );
                }

                return ListView.separated(
                  padding: const EdgeInsets.all(12),
                  itemCount: history.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final trip = history[index];
                    final routeId = trip['route_id']?.toString() ?? '';
                    final routeName = trip['route_name']?.toString() ?? routeId;
                    final tripId = trip['trip_id']?.toString() ?? '';
                    final vehicleId = trip['vehicle_id']?.toString() ?? '';
                    final origin = trip['origin']?.toString() ?? '';
                    final destination = trip['destination']?.toString() ?? '';
                    final startTime = trip['start_time']?.toString() ?? '';
                    final endTime = trip['end_time']?.toString() ?? '';
                    final actualStart = trip['actual_start_time']?.toString();
                    final actualEnd = trip['actual_end_time']?.toString();
                    final rawDuration = trip['duration']?.toString() ?? '';
                    final status = trip['status']?.toString() ?? 'completed';
                    final serviceDate = trip['service_date']?.toString() ?? '';

                    final displayStart = _formatTime(actualStart, startTime);
                    final displayEnd = _formatTime(actualEnd, endTime);
                    final displayDuration = _formatDuration(
                      actualStart,
                      actualEnd,
                      startTime,
                      endTime,
                      rawDuration,
                    );

                    return Container(
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: const Color(0xFFE2E8F0),
                          width: 1,
                        ),
                        boxShadow: const [
                          BoxShadow(
                            color: Color(0x0F000000),
                            blurRadius: 10,
                            offset: Offset(0, 3),
                          ),
                        ],
                      ),
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  routeName,
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w900,
                                    color: ink,
                                  ),
                                ),
                              ),
                              _buildStatusBadge(status),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Expanded(
                                child: Text(
                                  'Trip ID: $tripId',
                                  style: const TextStyle(color: muted, fontSize: 13),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 8),
                              if (serviceDate.isNotEmpty)
                                Text(
                                  'Date: $serviceDate',
                                  style: const TextStyle(color: muted, fontSize: 13),
                                ),
                            ],
                          ),
                          if (vehicleId.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(
                              'Vehicle: $vehicleId',
                              style: const TextStyle(color: muted, fontSize: 13),
                            ),
                          ],
                          const SizedBox(height: 14),
                          Row(
                            children: [
                              const Icon(Icons.circle, size: 10, color: green),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  origin.isNotEmpty ? origin : 'Origin',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 14,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          Container(
                            width: 2,
                            height: 16,
                            margin: const EdgeInsets.only(left: 4),
                            color: const Color(0xFFCBD5E1),
                          ),
                          Row(
                            children: [
                              const Icon(Icons.place, size: 12, color: danger),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  destination.isNotEmpty ? destination : 'Destination',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 14,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                          Row(
                            children: [
                              const Icon(Icons.access_time, size: 16, color: muted),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  '$displayStart - $displayEnd',
                                  style: const TextStyle(color: muted, fontSize: 13),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 12),
                              const Icon(Icons.hourglass_bottom, size: 16, color: muted),
                              const SizedBox(width: 4),
                              Text(
                                displayDuration,
                                style: const TextStyle(
                                  color: muted,
                                  fontSize: 13,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class DriverSettingsScreen extends StatefulWidget {
  const DriverSettingsScreen({super.key, required this.services});

  final DriverServices services;

  @override
  State<DriverSettingsScreen> createState() => _DriverSettingsScreenState();
}

class _DriverSettingsScreenState extends State<DriverSettingsScreen> {
  @override
  Widget build(BuildContext context) {
    final services = widget.services;

    return Scaffold(
      body: Column(
        children: [
          GreenTopBar(
            title: 'Settings',
            onBack: () => Navigator.pop(context),
          ),
          Expanded(
            child: ValueListenableBuilder<Map<String, dynamic>>(
              valueListenable: services.appSettings,
              builder: (context, settings, _) {
                return ValueListenableBuilder<DriverTripState>(
                  valueListenable: services.tripState,
                  builder: (context, tripState, _) {
                    return ListView(
                      padding: const EdgeInsets.all(12),
                      children: [
                        // PROFILE SECTION
                        _buildSectionHeader('Profile'),
                        Card(
                          elevation: 0,
                          color: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                            side: const BorderSide(color: Color(0xFFE2E8F0)),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              children: [
                                _buildProfileRow('Driver Name', 'Mohamed Ali'),
                                const Divider(height: 24, color: Color(0xFFF1F5F9)),
                                _buildProfileRow('Driver ID', tripState.driverId ?? 'driver_test_001'),
                                const Divider(height: 24, color: Color(0xFFF1F5F9)),
                                _buildProfileRow('Vehicle Assigned', tripState.active ? tripState.vehicleId : 'None'),
                                const Divider(height: 24, color: Color(0xFFF1F5F9)),
                                _buildProfileRow('Active Route', tripState.active ? tripState.routeId : 'None'),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),

                        // APP PREFERENCES SECTION
                        _buildSectionHeader('App Preferences'),
                        Card(
                          elevation: 0,
                          color: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                            side: const BorderSide(color: Color(0xFFE2E8F0)),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            child: Column(
                              children: [
                                // Theme Dropdown
                                _buildDropdownRow<String>(
                                  label: 'Theme',
                                  value: settings['theme']?.toString() ?? 'system',
                                  items: const [
                                    DropdownMenuItem(value: 'light', child: Text('Light Mode')),
                                    DropdownMenuItem(value: 'dark', child: Text('Dark Mode')),
                                    DropdownMenuItem(value: 'system', child: Text('System Default')),
                                  ],
                                  onChanged: (val) {
                                    if (val != null) {
                                      services.updateSetting('theme', val);
                                    }
                                  },
                                ),
                                const Divider(height: 8, color: Color(0xFFF1F5F9)),
                                // Language Dropdown
                                _buildDropdownRow<String>(
                                  label: 'Language',
                                  value: settings['language']?.toString() ?? 'en',
                                  items: const [
                                    DropdownMenuItem(value: 'en', child: Text('English')),
                                    DropdownMenuItem(value: 'ar', child: Text('العربية (Arabic)')),
                                  ],
                                  onChanged: (val) {
                                    if (val != null) {
                                      services.updateSetting('language', val);
                                    }
                                  },
                                ),
                                const Divider(height: 8, color: Color(0xFFF1F5F9)),
                                // Notifications Switch
                                _buildSwitchRow(
                                  label: 'Enable Notifications',
                                  value: settings['notificationsEnabled'] == true,
                                  onChanged: (val) {
                                    services.updateSetting('notificationsEnabled', val);
                                  },
                                ),
                                const Divider(height: 8, color: Color(0xFFF1F5F9)),
                                // Location Interval Dropdown
                                _buildDropdownRow<int>(
                                  label: 'Location Update Interval',
                                  value: settings['locationUpdateInterval'] as int? ?? 10,
                                  items: const [
                                    DropdownMenuItem(value: 5, child: Text('5 seconds')),
                                    DropdownMenuItem(value: 10, child: Text('10 seconds')),
                                    DropdownMenuItem(value: 30, child: Text('30 seconds')),
                                    DropdownMenuItem(value: 60, child: Text('60 seconds')),
                                  ],
                                  onChanged: (val) {
                                    if (val != null) {
                                      services.updateSetting('locationUpdateInterval', val);
                                    }
                                  },
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),

                        // OPERATIONS SECTION
                        _buildSectionHeader('Operations'),
                        Card(
                          elevation: 0,
                          color: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                            side: const BorderSide(color: Color(0xFFE2E8F0)),
                          ),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            child: Column(
                              children: [
                                _buildSwitchRow(
                                  label: 'Auto-Send GPS Location',
                                  value: settings['autoSendLocation'] == true,
                                  onChanged: (val) {
                                    services.updateSetting('autoSendLocation', val);
                                  },
                                ),
                                const Divider(height: 8, color: Color(0xFFF1F5F9)),
                                _buildSwitchRow(
                                  label: 'Keep Screen Awake',
                                  value: settings['keepScreenAwake'] == true,
                                  onChanged: (val) {
                                    services.updateSetting('keepScreenAwake', val);
                                  },
                                ),
                                const Divider(height: 8, color: Color(0xFFF1F5F9)),
                                _buildSwitchRow(
                                  label: 'Show Stop Advancement Helper',
                                  value: settings['showStopAdvancement'] == true,
                                  onChanged: (val) {
                                    services.updateSetting('showStopAdvancement', val);
                                  },
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),

                        // ACCOUNT SECTION
                        SizedBox(
                          height: 48,
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: () async {
                              try {
                                await services.logout();
                                if (context.mounted) {
                                  Navigator.of(context).pushAndRemoveUntil(
                                    MaterialPageRoute(builder: (_) => DriverLoginScreen(services: services)),
                                    (route) => false,
                                  );
                                }
                              } catch (e) {
                                showAppPopup(
                                  context,
                                  message: 'Failed to logout: ${e.toString().replaceFirst('Exception: ', '')}',
                                  isSuccess: false,
                                );
                              }
                            },
                            style: ElevatedButton.styleFrom(
                              backgroundColor: danger.withOpacity(0.1),
                              foregroundColor: danger,
                              elevation: 0,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                                side: const BorderSide(color: danger),
                              ),
                            ),
                            icon: const Icon(Icons.logout),
                            label: const Text(
                              'Logout',
                              style: TextStyle(fontWeight: FontWeight.bold),
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                        const Center(
                          child: Text(
                            'Settings are stored locally on SharedPreferences',
                            style: TextStyle(color: muted, fontSize: 11),
                          ),
                        ),
                        const SizedBox(height: 20),
                      ],
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 8, top: 4),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.bold,
          color: darkGreen,
        ),
      ),
    );
  }

  Widget _buildProfileRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(fontSize: 14, color: muted, fontWeight: FontWeight.w500)),
        Text(value, style: const TextStyle(fontSize: 14, color: ink, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildSwitchRow({
    required String label,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 14, color: ink, fontWeight: FontWeight.w600),
          ),
        ),
        Switch(
          value: value,
          onChanged: onChanged,
          activeColor: green,
        ),
      ],
    );
  }

  Widget _buildDropdownRow<T>({
    required String label,
    required T value,
    required List<DropdownMenuItem<T>> items,
    required ValueChanged<T?> onChanged,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Text(
            label,
            style: const TextStyle(fontSize: 14, color: ink, fontWeight: FontWeight.w600),
          ),
        ),
        DropdownButton<T>(
          value: value,
          items: items,
          onChanged: onChanged,
          underline: Container(),
          icon: const Icon(Icons.arrow_drop_down, color: muted),
          dropdownColor: Colors.white,
          style: const TextStyle(fontSize: 14, color: ink, fontFamily: 'Roboto'),
        ),
      ],
    );
  }
}

class _UserLocationMarker extends StatelessWidget {
  const _UserLocationMarker({super.key, this.heading});
  final double? heading;

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.blue.withOpacity(0.15),
          ),
        ),
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
        Container(
          width: 12,
          height: 12,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            color: Colors.blue,
          ),
        ),
        if (heading != null)
          Transform.rotate(
            angle: (heading! * 3.141592653589793) / 180,
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
          Colors.blue.withOpacity(0.4),
          Colors.blue.withOpacity(0.0),
        ],
      ).createShader(Rect.fromCircle(
          center: Offset(size.width / 2, size.height / 2),
          radius: size.width / 2))
      ..style = PaintingStyle.fill;

    final path = Path()
      ..moveTo(size.width / 2, size.height / 2)
      ..arcTo(
        Rect.fromCircle(
            center: Offset(size.width / 2, size.height / 2),
            radius: size.width / 2),
        -3.141592653589793 / 2 - 3.141592653589793 / 6,
        3.141592653589793 / 3,
        false,
      )
      ..close();

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _MapPin extends StatelessWidget {
  const _MapPin({
    required this.icon,
    required this.bg,
    required this.color,
  });

  final IconData icon;
  final Color bg;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Stack(
      alignment: Alignment.center,
      children: [
        Icon(Icons.location_on, color: bg, size: 36),
        Positioned(
          top: 4,
          child: Icon(icon, color: color, size: 16),
        ),
      ],
    );
  }
}
