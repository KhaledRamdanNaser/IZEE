import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' hide Path;

void main() {
  debugPrint('Supervisor API base URL: ${ApiConfig.baseUrl}');
  runApp(const IzeeSupervisorApp());
}

const green = Color(0xFF05A845);
const darkGreen = Color(0xFF04933D);
const paleGreen = Color(0xFFE9FBF2);
const ink = Color(0xFF101828);
const muted = Color(0xFF667085);
const bg = Color(0xFFF6F8FA);
const danger = Color(0xFFF20A18);
const blue = Color(0xFF2563EB);
const orange = Color(0xFFFF9900);
const purple = Color(0xFFA100F5);

class ApiConfig {
  const ApiConfig._();

  static const baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: String.fromEnvironment(
      'IZEE_API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000',
    ),
  );
}

class LiveVehicleRepository {
  LiveVehicleRepository({http.Client? client})
      : _client = client ?? http.Client();

  final http.Client _client;

  Future<List<SupervisorVehicle>> fetchLiveVehicles() async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/vehicles/live').replace(
      queryParameters: const {'limit': '100'},
    );
    final response =
        await _client.get(uri).timeout(const Duration(seconds: 10));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Live vehicles request failed (${response.statusCode})');
    }

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    final rows = (decoded['vehicles'] as List<dynamic>?) ?? const [];
    return rows
        .whereType<Map<String, dynamic>>()
        .map(SupervisorVehicle.fromApi)
        .toList(growable: false);
  }

  void dispose() {
    _client.close();
  }
}

class LiveVehiclesBuilder extends StatefulWidget {
  const LiveVehiclesBuilder({super.key, required this.builder});

  final Widget Function(
    BuildContext context,
    List<SupervisorVehicle> vehicles,
    String? error,
    bool loading,
  ) builder;

  @override
  State<LiveVehiclesBuilder> createState() => _LiveVehiclesBuilderState();
}

class _LiveVehiclesBuilderState extends State<LiveVehiclesBuilder> {
  final LiveVehicleRepository _repository = LiveVehicleRepository();
  Timer? _timer;
  List<SupervisorVehicle> _vehicles = vehicles;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _load());
  }

  Future<void> _load() async {
    try {
      final liveVehicles = await _repository.fetchLiveVehicles();
      if (!mounted) return;
      setState(() {
        _vehicles = liveVehicles.isEmpty ? vehicles : liveVehicles;
        _error = liveVehicles.isEmpty ? 'No live vehicle rows yet' : null;
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Cannot reach backend at ${ApiConfig.baseUrl}';
        _loading = false;
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _repository.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return widget.builder(context, _vehicles, _error, _loading);
  }
}

class IzeeSupervisorApp extends StatelessWidget {
  const IzeeSupervisorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'IZEE Supervisor',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: bg,
        colorScheme: ColorScheme.fromSeed(seedColor: green),
        fontFamily: 'Roboto',
      ),
      home: const SupervisorSplashScreen(),
    );
  }
}

class SupervisorSplashScreen extends StatefulWidget {
  const SupervisorSplashScreen({super.key});

  @override
  State<SupervisorSplashScreen> createState() => _SupervisorSplashScreenState();
}

class _SupervisorSplashScreenState extends State<SupervisorSplashScreen> {
  @override
  void initState() {
    super.initState();
    Timer(const Duration(milliseconds: 1300), () {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const SupervisorLoginScreen()),
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: green,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const RoundIcon(
                icon: Icons.directions_bus, size: 120, iconSize: 56),
            const SizedBox(height: 24),
            const Text(
              'IZEE',
              style: TextStyle(
                  color: Colors.white,
                  fontSize: 34,
                  fontWeight: FontWeight.w800),
            ),
            Container(
                width: 90,
                height: 1,
                margin: const EdgeInsets.symmetric(vertical: 10),
                color: Colors.white38),
            const Text('Field Supervisor App',
                style: TextStyle(color: Colors.white, fontSize: 16)),
            const SizedBox(height: 34),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(3, (index) {
                return Container(
                  width: 7,
                  height: 7,
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  decoration: BoxDecoration(
                      color: Colors.white.withOpacity(index == 1 ? 0.85 : 0.45),
                      shape: BoxShape.circle),
                );
              }),
            ),
          ],
        ),
      ),
    );
  }
}

class SupervisorLoginScreen extends StatefulWidget {
  const SupervisorLoginScreen({super.key});

  @override
  State<SupervisorLoginScreen> createState() => _SupervisorLoginScreenState();
}

class _SupervisorLoginScreenState extends State<SupervisorLoginScreen> {
  final _idController = TextEditingController(text: 'SUP-2024-089');
  final _passwordController = TextEditingController();
  bool _hidePassword = true;

  @override
  void dispose() {
    _idController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  void _signIn() {
    final text = _idController.text.trim();
    final supervisorId = text == 'SUP-2024-089'
        ? 'supervisor_2'
        : (text.isEmpty ? 'supervisor_1' : text);
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
          builder: (_) => SupervisorHomeScreen(supervisorId: supervisorId)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final cardWidth = width > 700 ? 430.0 : double.infinity;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(24, 28, 24, 38),
              decoration: const BoxDecoration(color: green),
              child: const Column(
                children: [
                  RoundIcon(
                      icon: Icons.directions_bus,
                      size: 72,
                      iconSize: 36,
                      white: true),
                  SizedBox(height: 16),
                  Text('IZEE',
                      style: TextStyle(
                          color: Colors.white,
                          fontSize: 24,
                          fontWeight: FontWeight.w800)),
                  SizedBox(height: 4),
                  Text('Field Supervisor Portal',
                      style: TextStyle(color: Colors.white, fontSize: 13)),
                ],
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: Center(
                  child: SizedBox(
                    width: cardWidth,
                    child: Column(
                      children: [
                        AppCard(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Secure Login',
                                  style: TextStyle(
                                      fontSize: 22,
                                      fontWeight: FontWeight.w800,
                                      color: ink)),
                              const SizedBox(height: 24),
                              FieldLabel(
                                label: 'Supervisor ID / Email',
                                child: TextField(
                                  controller: _idController,
                                  decoration: inputDecoration(
                                      'Enter your ID or email',
                                      Icons.mail_outline),
                                ),
                              ),
                              const SizedBox(height: 18),
                              FieldLabel(
                                label: 'Password / PIN',
                                child: TextField(
                                  controller: _passwordController,
                                  obscureText: _hidePassword,
                                  decoration: inputDecoration(
                                          'Enter your password',
                                          Icons.lock_outline)
                                      .copyWith(
                                    suffixIcon: IconButton(
                                      icon: Icon(
                                          _hidePassword
                                              ? Icons.visibility_outlined
                                              : Icons.visibility_off_outlined,
                                          color: muted),
                                      onPressed: () => setState(
                                          () => _hidePassword = !_hidePassword),
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(height: 24),
                              SizedBox(
                                width: double.infinity,
                                height: 54,
                                child: FilledButton(
                                    onPressed: _signIn,
                                    style: filledStyle(green),
                                    child: const Text('Sign In')),
                              ),
                              const Padding(
                                padding: EdgeInsets.symmetric(vertical: 24),
                                child: Divider(),
                              ),
                              SizedBox(
                                width: double.infinity,
                                height: 48,
                                child: OutlinedButton.icon(
                                  onPressed: _signIn,
                                  icon: const Icon(Icons.fingerprint,
                                      color: green),
                                  label: const Text('Login with Biometrics'),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 28),
                        const Text('Having trouble logging in?',
                            style: TextStyle(color: muted)),
                        TextButton(
                            onPressed: () {},
                            child: const Text('Contact Support',
                                style: TextStyle(fontWeight: FontWeight.w800))),
                      ],
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

class SupervisorHomeScreen extends StatefulWidget {
  const SupervisorHomeScreen({super.key, this.supervisorId = 'supervisor_1'});

  final String supervisorId;

  @override
  State<SupervisorHomeScreen> createState() => _SupervisorHomeScreenState();
}

class _SupervisorHomeScreenState extends State<SupervisorHomeScreen> {
  List<dynamic> _regions = [];
  bool _loadingRegions = true;
  String? _regionsError;

  @override
  void initState() {
    super.initState();
    _fetchRegions();
  }

  Future<void> _fetchRegions() async {
    try {
      final res = await http.get(Uri.parse(
          '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/regions'));
      if (res.statusCode == 200) {
        setState(() {
          _regions = jsonDecode(res.body) as List<dynamic>;
          _regionsError = null;
          _loadingRegions = false;
        });
      } else {
        debugPrint('Failed to load regions. Status: ${res.statusCode}');
        setState(() {
          _regionsError = 'Region unavailable';
          _loadingRegions = false;
        });
      }
    } catch (e) {
      debugPrint('Technical error loading regions: $e');
      setState(() {
        _regionsError = 'Region unavailable';
        _loadingRegions = false;
      });
    }
  }

  String _getSupervisorName() {
    if (widget.supervisorId == 'supervisor_1') return 'Fatima Said';
    if (widget.supervisorId == 'supervisor_2') return 'Ahmed Hassan';
    return widget.supervisorId;
  }

  String _getSubtitle() {
    final name = _getSupervisorName();
    if (_loadingRegions) return '$name - Loading regions...';
    if (_regionsError != null) return '$name - Region unavailable';
    if (_regions.isEmpty) return '$name - No region assigned';
    final regionNames =
        _regions.map((r) => r['region_name']?.toString() ?? '').join(', ');
    return '$name - $regionNames';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: supervisorAppBar(
        title: 'IZEE Supervisor',
        subtitle: _getSubtitle(),
        actions: [
          IconButton(
            onPressed: () {},
            icon: Badge.count(
                count: 1, child: const Icon(Icons.notifications_none)),
            color: Colors.white,
          ),
          IconButton(
            onPressed: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => const ProfileScreen())),
            icon: const Icon(Icons.person_outline),
            color: Colors.white,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await _fetchRegions();
        },
        child: LiveVehiclesBuilder(
          builder: (context, liveVehicles, liveError, loadingLiveVehicles) {
            return ListView(
              physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(14),
            children: [
              if (liveError != null) ...[
                LiveDataBanner(
                    message: liveError, loading: loadingLiveVehicles),
                const SizedBox(height: 12),
              ],
              LayoutBuilder(
                builder: (context, constraints) {
                  final compact = constraints.maxWidth < 720;
                  if (compact) {
                    return Column(
                      children: [
                        const SizedBox(
                            height: 126,
                            child: MetricTile(
                                icon: Icons.location_on_outlined,
                                value: '8',
                                label: 'Active Routes',
                                color: blue)),
                        const SizedBox(height: 12),
                        SizedBox(
                            height: 126,
                            child: MetricTile(
                                icon: Icons.directions_bus,
                                value: '${liveVehicles.length}',
                                label: 'Vehicles',
                                color: green)),
                        const SizedBox(height: 12),
                        const SizedBox(
                            height: 126,
                            child: MetricTile(
                                icon: Icons.warning_amber_outlined,
                                value: '3',
                                label: 'Alerts',
                                color: danger)),
                      ],
                    );
                  }
                  return GridView.count(
                    crossAxisCount: 3,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                    childAspectRatio: 3.2,
                    children: [
                      const MetricTile(
                          icon: Icons.location_on_outlined,
                          value: '8',
                          label: 'Active Routes',
                          color: blue),
                      MetricTile(
                          icon: Icons.directions_bus,
                          value: '${liveVehicles.length}',
                          label: 'Vehicles',
                          color: green),
                      const MetricTile(
                          icon: Icons.warning_amber_outlined,
                          value: '3',
                          label: 'Alerts',
                          color: danger),
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              const SectionTitle('Quick Actions'),
              LayoutBuilder(
                builder: (context, constraints) {
                  final compact = constraints.maxWidth < 720;
                  final tiles = [
                    ActionTile(
                      icon: Icons.location_on_outlined,
                      title: 'Live Monitoring',
                      subtitle: 'Track vehicles',
                      color: green,
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => const LiveMonitoringScreen())),
                    ),
                    ActionTile(
                      icon: Icons.assignment_ind_outlined,
                      title: 'Assignments',
                      subtitle: 'Driver duties',
                      color: orange,
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => DriverAssignmentsScreen(
                              supervisorId: widget.supervisorId))),
                    ),
                    ActionTile(
                      icon: Icons.warning_amber_outlined,
                      title: 'Report Incident',
                      subtitle: 'Quick report',
                      color: danger,
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => const ReportIncidentScreen())),
                    ),
                    ActionTile(
                      icon: Icons.trending_up,
                      title: 'Service Check',
                      subtitle: 'Log observation',
                      color: blue,
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => const ServiceObservationScreen())),
                    ),
                    ActionTile(
                      icon: Icons.chat_bubble_outline,
                      title: 'Control Center',
                      subtitle: 'Messages',
                      color: purple,
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(
                          builder: (_) => const ControlCenterScreen())),
                    ),
                  ];
                  if (compact) {
                    return Column(
                      children: [
                        for (final tile in tiles) ...[
                          SizedBox(height: 104, child: tile),
                          if (tile != tiles.last) const SizedBox(height: 12),
                        ],
                      ],
                    );
                  }
                  return GridView.count(
                    crossAxisCount: 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    mainAxisSpacing: 12,
                    crossAxisSpacing: 12,
                    childAspectRatio: 4.6,
                    children: tiles,
                  );
                },
              ),
              const SizedBox(height: 18),
              Row(
                children: [
                  const Expanded(child: SectionTitle('Map Overview')),
                  TextButton(
                    onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(
                            builder: (_) => const LiveMonitoringScreen())),
                    child: const Text('View Full Map ->'),
                  ),
                ],
              ),
              SupervisorMapPreview(vehicles: liveVehicles),
              const SizedBox(height: 18),
              const SectionTitle('Recent Alerts'),
              const AlertRow(
                  icon: Icons.warning_amber_outlined,
                  title: 'Vehicle V-002 delayed by 15 mins',
                  time: '5m ago',
                  color: orange),
              const AlertRow(
                  icon: Icons.report_problem_outlined,
                  title: 'Breakdown reported on Route 89',
                  time: '12m ago',
                  color: danger),
              const AlertRow(
                  icon: Icons.schedule,
                  title: 'Peak hours starting soon',
                  time: '18m ago',
                  color: blue),
              const SizedBox(height: 18),
              const SectionTitle('Monitored Vehicles'),
              ...liveVehicles
                  .map((vehicle) => VehicleListRow(vehicle: vehicle)),
            ],
          );
        },
      ),
    ),
  );
}
}

class LiveMonitoringScreen extends StatelessWidget {
  const LiveMonitoringScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: simpleBar(
        context,
        title: 'Live Monitoring',
        subtitle: 'Real-time vehicle tracking',
        color: green,
        actions: const [
          Icon(Icons.filter_alt_outlined),
          SizedBox(width: 18),
          Icon(Icons.layers_outlined),
          SizedBox(width: 14)
        ],
      ),
      body: LiveVehiclesBuilder(
        builder: (context, liveVehicles, liveError, loadingLiveVehicles) {
          return Column(
            children: [
              if (liveError != null)
                LiveDataBanner(
                    message: liveError, loading: loadingLiveVehicles),
              Expanded(
                flex: 7,
                child: Stack(
                  children: [
                    Positioned.fill(child: BigMap(vehicles: liveVehicles)),
                    Positioned(
                      top: 18,
                      left: 14,
                      child: AppCard(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: const [
                            Text('Status',
                                style: TextStyle(fontSize: 12, color: muted)),
                            SizedBox(height: 8),
                            LegendDot(label: 'Running', color: green),
                            LegendDot(label: 'Delayed', color: orange),
                            LegendDot(label: 'Stopped', color: danger),
                          ],
                        ),
                      ),
                    ),
                    const Positioned(right: 14, top: 18, child: MapTools()),
                  ],
                ),
              ),
              Expanded(
                flex: 3,
                child: Container(
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    borderRadius:
                        BorderRadius.vertical(top: Radius.circular(8)),
                    boxShadow: [
                      BoxShadow(color: Color(0x18000000), blurRadius: 12)
                    ],
                  ),
                  child: ListView(
                    padding: const EdgeInsets.all(14),
                    children: [
                      Center(
                          child: Container(
                              width: 38,
                              height: 3,
                              color: const Color(0xFFD0D5DD))),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          const Expanded(
                              child: SectionTitle('Active Vehicles')),
                          SegmentedButton<String>(
                            showSelectedIcon: false,
                            segments: const [
                              ButtonSegment(value: 'all', label: Text('All')),
                              ButtonSegment(
                                  value: 'route', label: Text('By Route')),
                            ],
                            selected: const {'all'},
                            onSelectionChanged: (_) {},
                          ),
                        ],
                      ),
                      ...liveVehicles
                          .map((vehicle) => VehicleListRow(vehicle: vehicle)),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class ReportIncidentScreen extends StatefulWidget {
  const ReportIncidentScreen({super.key});

  @override
  State<ReportIncidentScreen> createState() => _ReportIncidentScreenState();
}

class _ReportIncidentScreenState extends State<ReportIncidentScreen> {
  String _category = 'Vehicle Breakdown';
  String _severity = 'Medium';
  String _vehicle = 'Select a vehicle...';

  @override
  Widget build(BuildContext context) {
    final categories = [
      ['Service Delay', Icons.schedule],
      ['Vehicle Breakdown', Icons.warning_amber_outlined],
      ['Overcrowding', Icons.report_problem_outlined],
      ['Route Deviation', Icons.location_on_outlined],
      ['Accident', Icons.warning_amber_outlined],
      ['Other Issue', Icons.report_problem_outlined],
    ];
    return Scaffold(
      appBar: simpleBar(context,
          title: 'Report Incident',
          subtitle: 'Log irregularities and issues',
          color: danger),
      body: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          const InfoPanel(
            icon: Icons.location_on_outlined,
            title: 'Auto-detected Location',
            body:
                '30.0444 N, 31.2357 E\nNasr City, Cairo\nJun 15, 2026, 05:29 AM',
          ),
          const SizedBox(height: 18),
          const FieldTitle('Incident Category *'),
          GridView.count(
            crossAxisCount: MediaQuery.sizeOf(context).width < 720 ? 1 : 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: MediaQuery.sizeOf(context).width < 720 ? 5 : 7,
            children: categories.map((item) {
              final title = item[0] as String;
              final icon = item[1] as IconData;
              return SelectTile(
                selected: _category == title,
                title: title,
                icon: icon,
                selectedColor: danger,
                onTap: () => setState(() => _category = title),
              );
            }).toList(),
          ),
          const SizedBox(height: 18),
          const FieldTitle('Severity Level *'),
          Row(
            children: ['Low', 'Medium', 'High'].map((level) {
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: SelectTile(
                    selected: _severity == level,
                    title: level,
                    icon: Icons.circle,
                    selectedColor: orange,
                    onTap: () => setState(() => _severity = level),
                    centered: true,
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 18),
          FieldLabel(
            label: 'Related Vehicle (Optional)',
            child: DropdownButtonFormField<String>(
              value: _vehicle,
              decoration: inputDecoration('', Icons.directions_bus)
                  .copyWith(prefixIcon: null),
              items: ['Select a vehicle...', 'V-001', 'V-002', 'V-003', 'V-004']
                  .map((value) {
                return DropdownMenuItem(value: value, child: Text(value));
              }).toList(),
              onChanged: (value) =>
                  setState(() => _vehicle = value ?? _vehicle),
            ),
          ),
          const SizedBox(height: 18),
          FieldLabel(
            label: 'Additional Notes',
            child: TextField(
              minLines: 5,
              maxLines: 6,
              decoration: inputDecoration(
                      'Provide detailed description of the incident...',
                      Icons.notes)
                  .copyWith(prefixIcon: null),
            ),
          ),
          const SizedBox(height: 4),
          const Text('0/500 characters',
              style: TextStyle(color: muted, fontSize: 12)),
          const SizedBox(height: 18),
          const FieldTitle('Attach Photo (Optional)'),
          DottedUploadBox(onTap: () {}),
          const SizedBox(height: 26),
          SizedBox(
            height: 52,
            child: FilledButton.icon(
              onPressed: _category.isEmpty ? null : () {},
              style: filledStyle(danger),
              icon: const Icon(Icons.send_outlined),
              label: const Text('Submit Report'),
            ),
          ),
          const SizedBox(height: 14),
          const Center(
              child: Text(
                  'Report will be sent immediately to the control center',
                  style: TextStyle(color: muted, fontSize: 12))),
        ],
      ),
    );
  }
}

class ServiceObservationScreen extends StatefulWidget {
  const ServiceObservationScreen({super.key});

  @override
  State<ServiceObservationScreen> createState() =>
      _ServiceObservationScreenState();
}

class _ServiceObservationScreenState extends State<ServiceObservationScreen> {
  final Map<String, bool> _checks = {
    'Vehicle Cleanliness': true,
    'Driver Behavior': false,
    'Stop Adherence': true,
    'Schedule Compliance': false,
    'Passenger Comfort': false,
    'Safety Equipment': false,
  };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: simpleBar(context,
          title: 'Service Observation',
          subtitle: 'Quality & compliance check',
          color: blue),
      body: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          FieldLabel(
            label: 'Select Vehicle *',
            child: DropdownButtonFormField<String>(
              decoration: inputDecoration('', Icons.directions_bus)
                  .copyWith(prefixIcon: null),
              value: 'Choose vehicle to observe...',
              items: [
                'Choose vehicle to observe...',
                'V-001 - Route 45',
                'V-002 - Route 12',
                'V-004 - Route 89'
              ]
                  .map((value) =>
                      DropdownMenuItem(value: value, child: Text(value)))
                  .toList(),
              onChanged: (_) {},
            ),
          ),
          const SizedBox(height: 18),
          const FieldTitle('Service Quality Checklist'),
          ..._checks.entries.map((entry) => ObservationItem(
                title: entry.key,
                subtitle: observationSubtitle(entry.key),
                good: entry.value,
                onChanged: (good) => setState(() => _checks[entry.key] = good),
              )),
          const SizedBox(height: 16),
          const FieldTitle('Overall Service Rating'),
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 18),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.star, color: Color(0xFFF5C518), size: 30),
                Icon(Icons.star, color: Color(0xFFF5C518), size: 30),
                Icon(Icons.star, color: Color(0xFFF5C518), size: 30),
                Icon(Icons.star, color: Color(0xFFF5C518), size: 30),
                Icon(Icons.star, color: Color(0xFFF5C518), size: 30),
              ],
            ),
          ),
          FieldLabel(
            label: 'Qualitative Feedback & Notes',
            child: TextField(
              minLines: 5,
              maxLines: 6,
              decoration: inputDecoration(
                      'Share detailed observations, commendations, or areas for improvement...',
                      Icons.notes)
                  .copyWith(prefixIcon: null),
            ),
          ),
          const SizedBox(height: 18),
          AppCard(
            color: const Color(0xFFFFFBEA),
            borderColor: const Color(0xFFFDE68A),
            child: Column(
              children: [
                CheckboxListTile(
                    value: false,
                    onChanged: (_) {},
                    title: const Text('Recommend driver training')),
                CheckboxListTile(
                    value: false,
                    onChanged: (_) {},
                    title: const Text('Suggest vehicle maintenance')),
                CheckboxListTile(
                    value: false,
                    onChanged: (_) {},
                    title: const Text('Commend for excellent service')),
              ],
            ),
          ),
          const SizedBox(height: 26),
          SizedBox(
            height: 52,
            child: FilledButton.icon(
                onPressed: () {},
                style: filledStyle(blue),
                icon: const Icon(Icons.send_outlined),
                label: const Text('Submit Observation')),
          ),
          const SizedBox(height: 14),
          const Center(
              child: Text('Your feedback helps improve service quality',
                  style: TextStyle(color: muted, fontSize: 12))),
        ],
      ),
    );
  }
}

class ControlCenterScreen extends StatelessWidget {
  const ControlCenterScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: simpleBar(context,
          title: 'Control Center',
          subtitle: 'Active - 3 operators online',
          color: purple),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            color: Colors.white,
            child: const Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                QuickChip(label: 'Emergency', color: danger),
                QuickChip(label: 'Send Report', color: blue),
                QuickChip(label: 'Update Status', color: green),
                QuickChip(label: 'Request Support', color: orange),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.all(14),
              children: const [
                MessageBubble(
                    sender: 'Control Center',
                    text:
                        'Good morning Ahmed. Please monitor Route 45 closely today.',
                    time: '08:15'),
                MessageBubble(
                    sender: 'You',
                    text: 'Confirmed. I will prioritize Route 45 monitoring.',
                    time: '08:17',
                    mine: true),
                MessageBubble(
                    sender: 'Control Center',
                    text:
                        'Vehicle V-002 is showing delays. Can you investigate?',
                    time: '09:42'),
                MessageBubble(
                    sender: 'You',
                    text: 'On it. Heading to the location now.',
                    time: '09:45',
                    mine: true),
                MessageBubble(
                    sender: 'You',
                    text:
                        'V-002 experiencing minor traffic congestion. Should normalize in 10 mins.\n\nReport #R-1542',
                    time: '10:03',
                    mine: true),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(12),
            color: Colors.white,
            child: Row(
              children: [
                IconButton(
                    onPressed: () {}, icon: const Icon(Icons.attach_file)),
                Expanded(
                  child: TextField(
                    decoration: inputDecoration(
                            'Type your message...', Icons.message_outlined)
                        .copyWith(
                            prefixIcon: null,
                            contentPadding:
                                const EdgeInsets.symmetric(horizontal: 14)),
                  ),
                ),
                IconButton(
                    onPressed: () {},
                    icon: const Icon(Icons.send, color: purple)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  void _openEditProfileDialog(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (_) => const ProfileEditDialog(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: simpleBar(context,
          title: 'Profile & Settings',
          subtitle: 'Manage your account',
          color: green),
      body: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          AppCard(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                Row(
                  children: [
                    const CircleAvatar(
                        radius: 36,
                        backgroundColor: green,
                        child: Text('AH',
                            style:
                                TextStyle(color: Colors.white, fontSize: 22))),
                    const SizedBox(width: 18),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Ahmed Hassan',
                              style: TextStyle(
                                  fontSize: 20, fontWeight: FontWeight.w800)),
                          const SizedBox(height: 4),
                          const Text('Field Supervisor',
                              style: TextStyle(color: muted)),
                          const SizedBox(height: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                                color: paleGreen,
                                borderRadius: BorderRadius.circular(999)),
                            child: const Text('ID: SUP-2024-089',
                                style: TextStyle(
                                    color: green,
                                    fontWeight: FontWeight.w800,
                                    fontSize: 12)),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const Divider(height: 42),
                const Row(
                  children: [
                    Expanded(
                        child: SmallStat(label: 'Total Shifts', value: '247')),
                    Expanded(
                        child: SmallStat(label: 'Reports Filed', value: '892')),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          const SectionTitle('Assigned Zones & Routes'),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const ListTile(
                  leading: RoundIcon(
                      icon: Icons.location_on_outlined,
                      size: 42,
                      iconSize: 22,
                      color: blue),
                  title: Text('Zone East'),
                  subtitle: Text('Primary assignment'),
                  trailing: Badge(
                      label: Text('Active'),
                      backgroundColor: paleGreen,
                      textColor: green),
                ),
                const Divider(),
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 0, 16, 10),
                  child: Text('Monitored Routes:',
                      style: TextStyle(color: muted, fontSize: 12)),
                ),
                const Padding(
                  padding: EdgeInsets.fromLTRB(16, 0, 16, 16),
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      MiniRoute('Route 45'),
                      MiniRoute('Route 12'),
                      MiniRoute('Route 89'),
                      MiniRoute('Route 34'),
                      MiniRoute('Route 67'),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          const SectionTitle('Notification Preferences'),
          AppCard(
            child: Column(
              children: [
                SettingsSwitch(
                    title: 'Incident Alerts',
                    subtitle: 'High priority notifications',
                    value: true),
                SettingsSwitch(
                    title: 'Delay Notifications',
                    subtitle: 'Vehicle delay updates',
                    value: true),
                SettingsSwitch(
                    title: 'Control Center Messages',
                    subtitle: 'Direct communications',
                    value: true),
                SettingsSwitch(
                    title: 'Daily Briefings',
                    subtitle: 'Morning summary reports',
                    value: false),
              ],
            ),
          ),
          const SizedBox(height: 18),
          const SectionTitle('App Settings'),
          AppCard(
            child: const Column(
              children: [
                SettingsRow(
                    icon: Icons.language,
                    title: 'Language',
                    subtitle: 'English'),
                SettingsRow(
                    icon: Icons.dark_mode_outlined,
                    title: 'Theme',
                    subtitle: 'Light mode'),
                SettingsRow(
                    icon: Icons.shield_outlined,
                    title: 'Privacy & Security',
                    subtitle: 'Manage your data'),
                SettingsRow(
                    icon: Icons.help_outline,
                    title: 'Help & Support',
                    subtitle: 'FAQs and contact'),
              ],
            ),
          ),
          const SizedBox(height: 18),
          SizedBox(
            height: 50,
            child: OutlinedButton.icon(
              onPressed: () => _openEditProfileDialog(context),
              icon: const Icon(Icons.person_outline),
              label: const Text('Edit Profile Information'),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            height: 52,
            child: FilledButton.icon(
              onPressed: () => Navigator.of(context).pushAndRemoveUntil(
                MaterialPageRoute(
                    builder: (_) => const SupervisorLoginScreen()),
                (_) => false,
              ),
              style: filledStyle(danger),
              icon: const Icon(Icons.logout),
              label: const Text('Logout'),
            ),
          ),
          const SizedBox(height: 22),
          const Center(
              child: Text(
                  'IZEE Field Supervisor App\nVersion 2.1.0 - Build 2024.12\n© 2025 IZEE Smart Transportation',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: muted, fontSize: 12))),
        ],
      ),
    );
  }
}

class MetricTile extends StatelessWidget {
  const MetricTile(
      {super.key,
      required this.icon,
      required this.value,
      required this.label,
      required this.color});

  final IconData icon;
  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final tightHeight =
            constraints.hasBoundedHeight && constraints.maxHeight < 112;
        final iconBox = tightHeight ? 32.0 : 42.0;
        final iconGlyph = tightHeight ? 18.0 : 22.0;
        final spacing = tightHeight ? 4.0 : 10.0;
        final valueHeight = tightHeight ? 22.0 : 28.0;
        final valueFont = tightHeight ? 20.0 : 22.0;
        final labelFont = tightHeight ? 11.0 : 12.0;

        return AppCard(
          padding: EdgeInsets.symmetric(
            horizontal: tightHeight ? 6 : 16,
            vertical: tightHeight ? 4 : 14,
          ),
          child: LayoutBuilder(
            builder: (context, innerConstraints) {
              return Center(
                child: FittedBox(
                  fit: BoxFit.scaleDown,
                  child: SizedBox(
                    width: innerConstraints.hasBoundedWidth
                        ? innerConstraints.maxWidth
                        : 120,
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        RoundIcon(
                            icon: icon,
                            size: iconBox,
                            iconSize: iconGlyph,
                            color: color),
                        SizedBox(height: spacing),
                        SizedBox(
                          height: valueHeight,
                          child: FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(
                              value,
                              style: TextStyle(
                                  fontSize: valueFont,
                                  fontWeight: FontWeight.w800),
                            ),
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          textAlign: TextAlign.center,
                          style: TextStyle(color: muted, fontSize: labelFont),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        );
      },
    );
  }
}

class ProfileEditDialog extends StatefulWidget {
  const ProfileEditDialog({super.key});

  @override
  State<ProfileEditDialog> createState() => _ProfileEditDialogState();
}

class _ProfileEditDialogState extends State<ProfileEditDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _emailController;
  late final TextEditingController _phoneController;
  String _region = 'Zone East';
  bool _active = true;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: 'Ahmed Hassan');
    _emailController = TextEditingController(text: 'ahmed.hassan@izee.local');
    _phoneController = TextEditingController(text: '+20 100 123 4567');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  void _save() {
    if (!_formKey.currentState!.validate()) return;
    Navigator.of(context).pop();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Profile information updated locally')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit Profile Information'),
      content: SizedBox(
        width: 460,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: _nameController,
                  decoration: inputDecoration('Name', Icons.person_outline),
                  validator: (value) => (value == null || value.trim().isEmpty)
                      ? 'Name is required'
                      : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _emailController,
                  decoration: inputDecoration('Email', Icons.mail_outline),
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _phoneController,
                  decoration: inputDecoration('Phone', Icons.phone_outlined),
                  keyboardType: TextInputType.phone,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: _region,
                  decoration: inputDecoration('', Icons.map_outlined)
                      .copyWith(prefixIcon: null),
                  items: const [
                    'Zone East',
                    'Zone West',
                    'Zone North',
                    'Zone South'
                  ]
                      .map((region) =>
                          DropdownMenuItem(value: region, child: Text(region)))
                      .toList(),
                  onChanged: (value) =>
                      setState(() => _region = value ?? _region),
                ),
                const SizedBox(height: 4),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Active supervisor'),
                  value: _active,
                  activeColor: green,
                  onChanged: (value) => setState(() => _active = value),
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _save,
          style: filledStyle(green),
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class ActionTile extends StatelessWidget {
  const ActionTile(
      {super.key,
      required this.icon,
      required this.title,
      required this.subtitle,
      required this.color,
      required this.onTap});

  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      borderColor: color,
      child: Row(
        children: [
          RoundIcon(icon: icon, size: 44, iconSize: 22, color: color),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Text(subtitle,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: muted, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class LiveDataBanner extends StatelessWidget {
  const LiveDataBanner(
      {super.key, required this.message, required this.loading});

  final String message;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Row(
        children: [
          Icon(loading ? Icons.sync : Icons.info_outline,
              color: orange, size: 18),
          const SizedBox(width: 8),
          Expanded(
              child: Text(message,
                  style: const TextStyle(color: muted, fontSize: 12))),
        ],
      ),
    );
  }
}

class SupervisorMapPreview extends StatelessWidget {
  const SupervisorMapPreview({super.key, required this.vehicles});

  final List<SupervisorVehicle> vehicles;

  @override
  Widget build(BuildContext context) {
    final onTime = vehicles
        .where((vehicle) =>
            vehicle.status == 'Running' || vehicle.status == 'On Time')
        .length;
    final issues = vehicles.length - onTime;

    final markers = vehicles.map((vehicle) {
      final lon = vehicle.lon ?? (31.20 + vehicle.mapX * (31.45 - 31.20));
      final lat = vehicle.lat ?? (30.18 + vehicle.mapY * (29.95 - 30.18));
      return Marker(
        point: LatLng(lat, lon),
        width: 34,
        height: 34,
        child: Tooltip(
          message: '${vehicle.id} - ${vehicle.area}',
          child: MapVehicle(color: vehicle.color, compact: true),
        ),
      );
    }).toList();

    return SizedBox(
      height: 150,
      child: AppCard(
        padding: EdgeInsets.zero,
        child: Stack(
          children: [
            Positioned.fill(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: FlutterMap(
                  options: const MapOptions(
                    initialCenter: LatLng(30.0444, 31.2357),
                    initialZoom: 10.5,
                  ),
                  children: [
                    TileLayer(
                      urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                      userAgentPackageName: 'com.example.izee_supervisor',
                    ),
                    MarkerLayer(markers: markers),
                  ],
                ),
              ),
            ),
            Positioned(
                left: 34,
                bottom: 12,
                child: StatusPill(label: 'On Time: $onTime', color: green)),
            Positioned(
                left: 124,
                bottom: 12,
                child: StatusPill(label: 'Issues: $issues', color: danger)),
          ],
        ),
      ),
    );
  }
}

class BigMap extends StatelessWidget {
  const BigMap({super.key, required this.vehicles});

  final List<SupervisorVehicle> vehicles;

  @override
  Widget build(BuildContext context) {
    final markers = vehicles.map((vehicle) {
      final lon = vehicle.lon ?? (31.20 + vehicle.mapX * (31.45 - 31.20));
      final lat = vehicle.lat ?? (30.18 + vehicle.mapY * (29.95 - 30.18));
      return Marker(
        point: LatLng(lat, lon),
        width: 44,
        height: 44,
        child: Tooltip(
          message: '${vehicle.id} - ${vehicle.area}',
          child: MapVehicle(
            color: vehicle.color,
            pulse: vehicle.color == green,
            compact: false,
          ),
        ),
      );
    }).toList();

    return FlutterMap(
      options: const MapOptions(
        initialCenter: LatLng(30.0444, 31.2357),
        initialZoom: 11.5,
      ),
      children: [
        TileLayer(
          urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
          userAgentPackageName: 'com.example.izee_supervisor',
        ),
        MarkerLayer(markers: markers),
      ],
    );
  }
}

class MapGrid extends StatelessWidget {
  const MapGrid({super.key});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(painter: MapGridPainter());
  }
}

class MapGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final bgPaint = Paint()..color = const Color(0xFFEFFBF6);
    canvas.drawRect(Offset.zero & size, bgPaint);

    final line = Paint()
      ..color = const Color(0xFFE0E7EF)
      ..strokeWidth = 1;
    for (double x = 0; x < size.width; x += 82) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), line);
    }
    for (double y = 0; y < size.height; y += 54) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), line);
    }

    final road = Paint()
      ..color = const Color(0xFFC9D3DD)
      ..strokeWidth = 4;
    canvas.drawLine(Offset(0, size.height * .28),
        Offset(size.width, size.height * .28), road);
    canvas.drawLine(Offset(0, size.height * .62),
        Offset(size.width, size.height * .62), road);
    canvas.drawLine(Offset(size.width * .25, 0),
        Offset(size.width * .25, size.height), road);
    canvas.drawLine(
        Offset(size.width * .5, 0), Offset(size.width * .5, size.height), road);
    canvas.drawLine(Offset(size.width * .75, 0),
        Offset(size.width * .75, size.height), road);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class MapVehicle extends StatelessWidget {
  const MapVehicle(
      {super.key,
      required this.color,
      this.pulse = false,
      this.compact = false});

  final Color color;
  final bool pulse;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final size = compact ? 20.0 : 34.0;
    return Stack(
      alignment: Alignment.center,
      children: [
        if (pulse)
          Container(
            width: size * 2,
            height: size * 2,
            decoration: BoxDecoration(
                color: color.withOpacity(.18),
                shape: BoxShape.circle,
                border: Border.all(color: color.withOpacity(.35), width: 2)),
          ),
        Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
              color: color,
              shape: BoxShape.circle,
              boxShadow: const [
                BoxShadow(color: Color(0x22000000), blurRadius: 8)
              ]),
          child: Icon(Icons.directions_bus,
              color: Colors.white, size: compact ? 12 : 19),
        ),
      ],
    );
  }
}

class VehicleListRow extends StatelessWidget {
  const VehicleListRow({super.key, required this.vehicle});

  final SupervisorVehicle vehicle;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          RoundIcon(
              icon: Icons.directions_bus,
              size: 42,
              iconSize: 20,
              color: vehicle.color),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(vehicle.id,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                Text(vehicle.route,
                    style: const TextStyle(color: muted, fontSize: 12)),
                if (vehicle.speed != null)
                  Text('${vehicle.speed} km/h - ${vehicle.passengers} pax',
                      style: const TextStyle(color: muted, fontSize: 12)),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              StatusPill(label: vehicle.status, color: vehicle.color),
              const SizedBox(height: 6),
              Text(vehicle.area,
                  style: const TextStyle(color: muted, fontSize: 12)),
            ],
          ),
        ],
      ),
    );
  }
}

class ObservationItem extends StatelessWidget {
  const ObservationItem(
      {super.key,
      required this.title,
      required this.subtitle,
      required this.good,
      required this.onChanged});

  final String title;
  final String subtitle;
  final bool good;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(subtitle, style: const TextStyle(color: muted, fontSize: 12)),
          const SizedBox(height: 22),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => onChanged(true),
                  style: OutlinedButton.styleFrom(
                      backgroundColor: good ? paleGreen : null),
                  icon: const Icon(Icons.check_circle_outline),
                  label: const Text('Good'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => onChanged(false),
                  style: OutlinedButton.styleFrom(
                      backgroundColor: !good ? const Color(0xFFFFF1F2) : null),
                  icon: const Icon(Icons.cancel_outlined),
                  label: const Text('Poor'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class MessageBubble extends StatelessWidget {
  const MessageBubble(
      {super.key,
      required this.sender,
      required this.text,
      required this.time,
      this.mine = false});

  final String sender;
  final String text;
  final String time;
  final bool mine;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        width: MediaQuery.sizeOf(context).width > 800
            ? 360
            : MediaQuery.sizeOf(context).width * .78,
        margin: const EdgeInsets.only(bottom: 18),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: mine ? green : Colors.white,
          borderRadius: BorderRadius.circular(8),
          boxShadow: const [BoxShadow(color: Color(0x11000000), blurRadius: 8)],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(sender,
                style: TextStyle(
                    color: mine ? Colors.white70 : blue,
                    fontSize: 12,
                    fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Text(text, style: TextStyle(color: mine ? Colors.white : ink)),
            const SizedBox(height: 10),
            Align(
                alignment: Alignment.centerRight,
                child: Text(time,
                    style: TextStyle(
                        color: mine ? Colors.white70 : muted, fontSize: 12))),
          ],
        ),
      ),
    );
  }
}

class AppCard extends StatelessWidget {
  const AppCard(
      {super.key,
      required this.child,
      this.padding = const EdgeInsets.all(16),
      this.margin,
      this.onTap,
      this.borderColor,
      this.color = Colors.white});

  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final VoidCallback? onTap;
  final Color? borderColor;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final card = Container(
      margin: margin,
      padding: padding,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: borderColor ?? const Color(0xFFE5E7EB)),
        boxShadow: const [
          BoxShadow(
              color: Color(0x11000000), blurRadius: 8, offset: Offset(0, 3))
        ],
      ),
      child: child,
    );
    if (onTap == null) return card;
    return Material(
        color: Colors.transparent,
        child: InkWell(
            borderRadius: BorderRadius.circular(8), onTap: onTap, child: card));
  }
}

class RoundIcon extends StatelessWidget {
  const RoundIcon(
      {super.key,
      required this.icon,
      this.size = 48,
      this.iconSize = 24,
      this.white = false,
      this.color = green});

  final IconData icon;
  final double size;
  final double iconSize;
  final bool white;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
          color: white ? Colors.white : color.withOpacity(.12),
          shape: BoxShape.circle),
      child: Icon(icon, color: white ? green : color, size: iconSize),
    );
  }
}

class SelectTile extends StatelessWidget {
  const SelectTile(
      {super.key,
      required this.selected,
      required this.title,
      required this.icon,
      required this.selectedColor,
      required this.onTap,
      this.centered = false});

  final bool selected;
  final String title;
  final IconData icon;
  final Color selectedColor;
  final VoidCallback onTap;
  final bool centered;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      borderColor: selected ? selectedColor : null,
      color: selected ? selectedColor.withOpacity(.06) : Colors.white,
      child: centered
          ? Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon,
                    color: selected ? selectedColor : const Color(0xFFE5E7EB),
                    size: 28),
                const SizedBox(height: 8),
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
              ],
            )
          : Row(children: [
              Icon(icon, color: selected ? selectedColor : muted),
              const SizedBox(width: 12),
              Expanded(
                  child: Text(title,
                      style: const TextStyle(fontWeight: FontWeight.w700)))
            ]),
    );
  }
}

class FieldLabel extends StatelessWidget {
  const FieldLabel({super.key, required this.label, required this.child});

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label,
          style: const TextStyle(
              fontWeight: FontWeight.w800, color: Color(0xFF344054))),
      const SizedBox(height: 8),
      child
    ]);
  }
}

class FieldTitle extends StatelessWidget {
  const FieldTitle(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text(text,
            style: const TextStyle(
                fontWeight: FontWeight.w800, color: Color(0xFF344054))));
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text(text,
            style: const TextStyle(
                fontWeight: FontWeight.w800, color: Color(0xFF344054))));
  }
}

class AlertRow extends StatelessWidget {
  const AlertRow(
      {super.key,
      required this.icon,
      required this.title,
      required this.time,
      required this.color});

  final IconData icon;
  final String title;
  final String time;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          RoundIcon(icon: icon, size: 40, iconSize: 20, color: color),
          const SizedBox(width: 12),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w700)),
                Text(time, style: const TextStyle(color: muted, fontSize: 12))
              ])),
        ],
      ),
    );
  }
}

class InfoPanel extends StatelessWidget {
  const InfoPanel(
      {super.key, required this.icon, required this.title, required this.body});

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      color: const Color(0xFFEFF6FF),
      borderColor: const Color(0xFFBFDBFE),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: blue),
          const SizedBox(width: 12),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Text(body,
                    style:
                        const TextStyle(color: Color(0xFF344054), height: 1.4))
              ])),
        ],
      ),
    );
  }
}

class DottedUploadBox extends StatelessWidget {
  const DottedUploadBox({super.key, required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 86,
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
                color: const Color(0xFFD0D5DD), style: BorderStyle.solid)),
        child: const Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.camera_alt_outlined, color: muted),
          SizedBox(height: 8),
          Text('Tap to capture or upload photo', style: TextStyle(color: muted))
        ])),
      ),
    );
  }
}

class LegendDot extends StatelessWidget {
  const LegendDot({super.key, required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
            width: 9,
            height: 9,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 8),
        Text(label, style: const TextStyle(fontSize: 12))
      ]),
    );
  }
}

class MapTools extends StatelessWidget {
  const MapTools({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(children: const [
      MapToolButton(icon: Icons.add),
      SizedBox(height: 10),
      MapToolButton(icon: Icons.remove),
      SizedBox(height: 10),
      MapToolButton(icon: Icons.near_me_outlined)
    ]);
  }
}

class MapToolButton extends StatelessWidget {
  const MapToolButton({super.key, required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(8),
          boxShadow: const [
            BoxShadow(color: Color(0x22000000), blurRadius: 8)
          ]),
      child: Icon(icon, color: ink),
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration:
          BoxDecoration(color: color, borderRadius: BorderRadius.circular(999)),
      child: Text(label,
          style: const TextStyle(
              color: Colors.white, fontSize: 11, fontWeight: FontWeight.w800)),
    );
  }
}

class QuickChip extends StatelessWidget {
  const QuickChip({super.key, required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      decoration: BoxDecoration(
          color: color.withOpacity(.12),
          borderRadius: BorderRadius.circular(999)),
      child: Text(label,
          style: TextStyle(
              color: color, fontSize: 12, fontWeight: FontWeight.w800)),
    );
  }
}

class SmallStat extends StatelessWidget {
  const SmallStat({super.key, required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: const TextStyle(color: muted, fontSize: 12)),
      const SizedBox(height: 8),
      Text(value,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800))
    ]);
  }
}

class MiniRoute extends StatelessWidget {
  const MiniRoute(this.label, {super.key});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
          color: const Color(0xFFEFF4FF),
          borderRadius: BorderRadius.circular(999)),
      child: Text(label,
          style: const TextStyle(
              color: Color(0xFF344054),
              fontSize: 12,
              fontWeight: FontWeight.w800)),
    );
  }
}

class SettingsSwitch extends StatefulWidget {
  const SettingsSwitch(
      {super.key,
      required this.title,
      required this.subtitle,
      required this.value});

  final String title;
  final String subtitle;
  final bool value;

  @override
  State<SettingsSwitch> createState() => _SettingsSwitchState();
}

class _SettingsSwitchState extends State<SettingsSwitch> {
  late bool _value = widget.value;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.notifications_none, color: muted),
      title: Text(widget.title,
          style: const TextStyle(fontWeight: FontWeight.w800)),
      subtitle: Text(widget.subtitle),
      trailing: Switch(
          value: _value,
          activeColor: green,
          onChanged: (value) => setState(() => _value = value)),
    );
  }
}

class SettingsRow extends StatelessWidget {
  const SettingsRow(
      {super.key,
      required this.icon,
      required this.title,
      required this.subtitle});

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: muted),
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_right, color: muted),
    );
  }
}

PreferredSizeWidget supervisorAppBar(
    {required String title,
    required String subtitle,
    List<Widget> actions = const []}) {
  return AppBar(
    backgroundColor: green,
    foregroundColor: Colors.white,
    toolbarHeight: 72,
    title: Row(
      children: [
        const Icon(Icons.directions_bus, size: 22),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(fontWeight: FontWeight.w800),
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
                softWrap: false,
              ),
              Text(
                subtitle,
                style: const TextStyle(fontSize: 12, color: Colors.white),
                overflow: TextOverflow.ellipsis,
                maxLines: 1,
                softWrap: false,
              ),
            ],
          ),
        ),
      ],
    ),
    actions: actions,
  );
}

PreferredSizeWidget simpleBar(BuildContext context,
    {required String title,
    required String subtitle,
    required Color color,
    List<Widget> actions = const []}) {
  return AppBar(
    backgroundColor: color,
    foregroundColor: Colors.white,
    toolbarHeight: 58,
    leading: IconButton(
        icon: const Icon(Icons.arrow_back),
        onPressed: () => Navigator.of(context).maybePop()),
    title: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(fontWeight: FontWeight.w800),
          overflow: TextOverflow.ellipsis,
          maxLines: 1,
          softWrap: false,
        ),
        Text(
          subtitle,
          style: const TextStyle(fontSize: 12, color: Colors.white),
          overflow: TextOverflow.ellipsis,
          maxLines: 1,
          softWrap: false,
        ),
      ],
    ),
    actions: actions,
  );
}

InputDecoration inputDecoration(String hint, IconData icon) {
  return InputDecoration(
    hintText: hint,
    prefixIcon: Icon(icon, color: muted),
    filled: true,
    fillColor: const Color(0xFFF4F6F8),
    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFFD0D5DD))),
    enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFFD0D5DD))),
    focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: green, width: 1.5)),
  );
}

ButtonStyle filledStyle(Color color) {
  return FilledButton.styleFrom(
    backgroundColor: color,
    foregroundColor: Colors.white,
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    textStyle: const TextStyle(fontWeight: FontWeight.w800),
  );
}

String observationSubtitle(String title) {
  return switch (title) {
    'Vehicle Cleanliness' => 'Interior and exterior condition',
    'Driver Behavior' => 'Professional conduct and courtesy',
    'Stop Adherence' => 'Proper stops at designated locations',
    'Schedule Compliance' => 'Timely departure and arrival',
    'Passenger Comfort' => 'Seating, AC, and ride quality',
    _ => 'Fire extinguisher, first aid, etc.',
  };
}

class SupervisorVehicle {
  const SupervisorVehicle(
    this.id,
    this.route,
    this.status,
    this.area,
    this.color, {
    this.speed,
    this.passengers,
    this.lat,
    this.lon,
    this.mapX = .5,
    this.mapY = .5,
  });

  factory SupervisorVehicle.fromApi(Map<String, dynamic> data) {
    final statusKey = (data['status'] ?? 'running').toString().toLowerCase();
    final speedValue = data['speed_kmh'];
    final latValue = (data['lat'] as num?)?.toDouble();
    final lonValue = (data['lon'] as num?)?.toDouble();
    final id = (data['vehicle_id'] ?? 'Unknown vehicle').toString();
    final status = switch (statusKey) {
      'stale' => 'Stale',
      'stopped' => 'Stopped',
      _ => 'Running',
    };
    final color = switch (statusKey) {
      'stale' => orange,
      'stopped' => danger,
      _ => green,
    };

    return SupervisorVehicle(
      id,
      'Live vehicle',
      status,
      (data['area'] ?? _formatLatLon(latValue, lonValue)).toString(),
      color,
      speed: speedValue is num ? speedValue.round() : null,
      passengers: 0,
      lat: latValue,
      lon: lonValue,
      mapX: _normalize(lonValue, 31.20, 31.45),
      mapY: _normalize(latValue, 30.18, 29.95),
    );
  }

  final String id;
  final String route;
  final String status;
  final String area;
  final Color color;
  final int? speed;
  final int? passengers;
  final double? lat;
  final double? lon;
  final double mapX;
  final double mapY;
}

const vehicles = [
  SupervisorVehicle('V-001', 'Route 45', 'On Time', 'Nasr City', green,
      speed: 45, passengers: 28, mapX: .18, mapY: .28),
  SupervisorVehicle('V-002', 'Route 12', 'Delayed', 'Downtown', orange,
      speed: 25, passengers: 35, mapX: .35, mapY: .46),
  SupervisorVehicle('V-003', 'Route 45', 'On Time', 'Heliopolis', green,
      speed: 38, passengers: 22, mapX: .52, mapY: .38),
  SupervisorVehicle('V-004', 'Route 89', 'Incident', 'Zamalek', danger,
      speed: 0, passengers: 18, mapX: .68, mapY: .30),
  SupervisorVehicle('V-005', 'Route 12', 'On Time', 'Maadi', green,
      speed: 41, passengers: 30, mapX: .82, mapY: .64),
];

double _normalize(double? value, double min, double max) {
  if (value == null || min == max) return .5;
  final normalized = (value - min) / (max - min);
  return normalized.clamp(.08, .92).toDouble();
}

String _formatLatLon(double? lat, double? lon) {
  if (lat == null || lon == null) return 'Unknown location';
  return '${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}';
}

class DriverAssignmentsScreen extends StatefulWidget {
  const DriverAssignmentsScreen(
      {super.key, this.supervisorId = 'supervisor_1'});

  final String supervisorId;

  @override
  State<DriverAssignmentsScreen> createState() =>
      _DriverAssignmentsScreenState();
}

class _DriverAssignmentsScreenState extends State<DriverAssignmentsScreen> {
  List<dynamic> _assignments = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _fetchAssignments();
  }

  Future<void> _fetchAssignments() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await http.get(Uri.parse(
          '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/assignments'));
      if (res.statusCode == 200) {
        debugPrint('ASSIGNMENTS_REFRESH_RESPONSE: ${res.body}');
        setState(() {
          _assignments = jsonDecode(res.body) as List<dynamic>;
          _loading = false;
        });
      } else {
        debugPrint('Failed to load assignments. Status: ${res.statusCode}');
        setState(() {
          _error = 'Unable to connect to the server. Please check that the backend is running and try again.';
          _loading = false;
        });
      }
    } catch (e) {
      debugPrint('Technical error fetching assignments: $e');
      setState(() {
        _error = 'Unable to connect to the server. Please check that the backend is running and try again.';
        _loading = false;
      });
    }
  }

  Future<void> _cancelAssignment(String assignmentId) async {
    final reason = await _askCancellationReason();
    if (reason == null) return;
    debugPrint(
        'CANCEL_ASSIGNMENT_REQUEST: assignment_id=$assignmentId reason=$reason');
    try {
      final res = await http.post(
        Uri.parse(
            '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/assignments/$assignmentId/cancel'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'supervisor_id': widget.supervisorId,
          'reason': reason,
        }),
      );
      if (res.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Assignment cancelled successfully')),
        );
        _fetchAssignments();
      } else {
        final err =
            jsonDecode(res.body)['detail'] ?? 'Failed to cancel assignment';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $err')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Network error: $e')),
      );
    }
  }

  Future<String?> _askCancellationReason() async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel Assignment'),
        content: TextField(
          controller: controller,
          autofocus: true,
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(
            labelText: 'Why are you cancelling this assignment?',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Keep Assignment'),
          ),
          FilledButton(
            onPressed: () {
              final text = controller.text.trim();
              Navigator.pop(
                  context, text.isEmpty ? 'Cancelled by supervisor' : text);
            },
            style: filledStyle(danger),
            child: const Text('Cancel Assignment'),
          ),
        ],
      ),
    );
    controller.dispose();
    return result;
  }

  Future<void> _deleteAssignment(String assignmentId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Assignment'),
        content: const Text(
            'This will hide the assignment from Supervisor and Driver screens but keep it in the database for audit.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: filledStyle(danger),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    debugPrint('DELETE_ASSIGNMENT_REQUEST: assignment_id=$assignmentId');
    try {
      final request = http.Request(
        'DELETE',
        Uri.parse(
            '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/assignments/$assignmentId'),
      )
        ..headers['Content-Type'] = 'application/json'
        ..body = jsonEncode({'supervisor_id': widget.supervisorId});
      final streamed = await request.send();
      final res = await http.Response.fromStream(streamed);
      if (res.statusCode >= 200 && res.statusCode < 300) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Assignment deleted')),
        );
        _fetchAssignments();
      } else {
        final err =
            jsonDecode(res.body)['detail'] ?? 'Failed to delete assignment';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $err')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Network error: $e')),
      );
    }
  }

  void _openCreateOrEditForm([Map<String, dynamic>? assignment]) {
    if (assignment != null) {
      debugPrint('EDIT_ASSIGNMENT_OPENED: $assignment');
      final status =
          (assignment['status']?.toString() ?? 'scheduled').toLowerCase();
      if (status != 'scheduled') {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Only scheduled assignments can be edited.')),
        );
        return;
      }
      showDialog<void>(
        context: context,
        builder: (_) => AssignmentEditDialog(
          supervisorId: widget.supervisorId,
          assignment: assignment,
          onSave: _fetchAssignments,
        ),
      );
      return;
    }

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AssignmentFormScreen(
          supervisorId: widget.supervisorId,
          onSave: () => _fetchAssignments(),
        ),
      ),
    );
  }

  String _assignmentDurationLabel(String startTime, String endTime) {
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
      appBar: simpleBar(
        context,
        title: 'Driver Assignments',
        subtitle: 'Manage duty assignments',
        color: orange,
      ),
      body: RefreshIndicator(
        onRefresh: _fetchAssignments,
        child: _loading
            ? Center(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: const [
                    CircularProgressIndicator(color: orange),
                    SizedBox(height: 16),
                    Text(
                      'Loading assignments...',
                      style: TextStyle(color: muted),
                    ),
                  ],
                ),
              )
            : _error != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline,
                              color: danger, size: 48),
                          const SizedBox(height: 12),
                          Text(_error!,
                              textAlign: TextAlign.center,
                              style: const TextStyle(color: muted)),
                          const SizedBox(height: 16),
                          ElevatedButton(
                            onPressed: _fetchAssignments,
                            style: filledStyle(orange),
                            child: const Text('Retry'),
                          )
                        ],
                      ),
                    ),
                  )
                : _assignments.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.assignment_outlined,
                                color: muted, size: 48),
                            const SizedBox(height: 12),
                            const Text('No assignments found. Create a new assignment.',
                                style: TextStyle(color: muted)),
                            const SizedBox(height: 16),
                            ElevatedButton(
                              onPressed: () => _openCreateOrEditForm(),
                              style: filledStyle(orange),
                              child: const Text('Create Assignment'),
                            ),
                          ],
                        ),
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.all(14),
                        itemCount: _assignments.length,
                        separatorBuilder: (_, __) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final item =
                              _assignments[index] as Map<String, dynamic>;
                          final assignmentId =
                              item['assignment_id']?.toString() ?? '';
                          final routeId = item['route_id']?.toString() ?? '';
                          final routeName =
                              item['route_name']?.toString() ?? routeId;
                          final driverId = item['driver_id']?.toString() ?? '';
                          final vehicleId =
                              item['vehicle_id']?.toString() ?? '';
                          final serviceDate =
                              item['service_date']?.toString() ?? '';
                          final startTime = item['start_time']?.toString() ??
                              item['planned_start_time']?.toString() ??
                              '';
                          final endTime = item['end_time']?.toString() ??
                              item['planned_end_time']?.toString() ??
                              '';
                          final status =
                              (item['status']?.toString() ?? 'scheduled')
                                  .toLowerCase();
                          final notes = item['notes']?.toString() ?? '';
                          final tripId = item['trip_id']?.toString() ?? '';

                          Color statusColor;
                          Color statusBg;
                          if (status == 'active') {
                            statusColor = darkGreen;
                            statusBg = green.withOpacity(0.12);
                          } else if (status == 'completed') {
                            statusColor = purple;
                            statusBg = purple.withOpacity(0.12);
                          } else if (status == 'cancelled') {
                            statusColor = danger;
                            statusBg = danger.withOpacity(0.12);
                          } else {
                            statusColor = muted;
                            statusBg = const Color(0xFFF1F5F9);
                          }

                          return AppCard(
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
                                            fontSize: 17,
                                            fontWeight: FontWeight.w800,
                                            color: ink),
                                      ),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 8, vertical: 4),
                                      decoration: BoxDecoration(
                                          color: statusBg,
                                          borderRadius:
                                              BorderRadius.circular(12)),
                                      child: Text(
                                        status.toUpperCase(),
                                        style: TextStyle(
                                            color: statusColor,
                                            fontSize: 10,
                                            fontWeight: FontWeight.w800),
                                      ),
                                    ),
                                    PopupMenuButton<String>(
                                      tooltip: 'Assignment actions',
                                      onSelected: (value) {
                                        if (value == 'edit') {
                                          _openCreateOrEditForm(item);
                                        } else if (value == 'cancel') {
                                          _cancelAssignment(assignmentId);
                                        } else if (value == 'delete') {
                                          _deleteAssignment(assignmentId);
                                        }
                                      },
                                      itemBuilder: (context) => const [
                                        PopupMenuItem(
                                          value: 'edit',
                                          child: ListTile(
                                            dense: true,
                                            leading: Icon(Icons.edit_outlined),
                                            title: Text('Edit Assignment'),
                                          ),
                                        ),
                                        PopupMenuItem(
                                          value: 'cancel',
                                          child: ListTile(
                                            dense: true,
                                            leading:
                                                Icon(Icons.cancel_outlined),
                                            title: Text('Cancel Assignment'),
                                          ),
                                        ),
                                        PopupMenuItem(
                                          value: 'delete',
                                          child: ListTile(
                                            dense: true,
                                            leading:
                                                Icon(Icons.delete_outline),
                                            title: Text('Delete Assignment'),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                if (tripId.isNotEmpty) ...[
                                  Text('Trip ID: $tripId',
                                      style: const TextStyle(
                                          color: muted, fontSize: 13)),
                                  const SizedBox(height: 4),
                                ],
                                Text('Driver ID: $driverId',
                                    style: const TextStyle(
                                        color: ink,
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600)),
                                const SizedBox(height: 4),
                                Text('Vehicle ID: $vehicleId',
                                    style: const TextStyle(
                                        color: ink,
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600)),
                                const SizedBox(height: 4),
                                Text(
                                    'Schedule: $serviceDate ($startTime - $endTime)',
                                    style: const TextStyle(
                                        color: muted, fontSize: 13)),
                                const SizedBox(height: 4),
                                Text(
                                    _assignmentDurationLabel(
                                        startTime, endTime),
                                    style: const TextStyle(
                                        color: muted, fontSize: 13)),
                                if (notes.isNotEmpty) ...[
                                  const SizedBox(height: 6),
                                  Text('Notes: $notes',
                                      style: const TextStyle(
                                          color: muted,
                                          fontStyle: FontStyle.italic,
                                          fontSize: 13)),
                                ],
                              ],
                            ),
                          );
                        },
                      ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _openCreateOrEditForm(),
        backgroundColor: orange,
        foregroundColor: Colors.white,
        child: const Icon(Icons.add),
      ),
    );
  }
}

class AssignmentEditDialog extends StatefulWidget {
  const AssignmentEditDialog({
    super.key,
    required this.supervisorId,
    required this.assignment,
    required this.onSave,
  });

  final String supervisorId;
  final Map<String, dynamic> assignment;
  final VoidCallback onSave;

  @override
  State<AssignmentEditDialog> createState() => _AssignmentEditDialogState();
}

class _AssignmentEditDialogState extends State<AssignmentEditDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _driverController;
  late final TextEditingController _vehicleController;
  late final TextEditingController _routeController;
  late final TextEditingController _notesController;
  late DateTime _serviceDate;
  late TimeOfDay _startTime;
  late TimeOfDay _endTime;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    final assignment = widget.assignment;
    _driverController =
        TextEditingController(text: assignment['driver_id']?.toString() ?? '');
    _vehicleController =
        TextEditingController(text: assignment['vehicle_id']?.toString() ?? '');
    _routeController =
        TextEditingController(text: assignment['route_id']?.toString() ?? '');
    _notesController =
        TextEditingController(text: assignment['notes']?.toString() ?? '');
    _serviceDate = _parseDate(assignment['service_date']?.toString());
    _startTime = _parseTime(assignment['start_time']?.toString() ??
        assignment['planned_start_time']?.toString() ??
        '08:00');
    _endTime = _parseTime(assignment['end_time']?.toString() ??
        assignment['planned_end_time']?.toString() ??
        '10:00');
  }

  @override
  void dispose() {
    _driverController.dispose();
    _vehicleController.dispose();
    _routeController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  DateTime _parseDate(String? value) {
    if (value == null || value.isEmpty) return DateTime.now();
    return DateTime.tryParse(value) ?? DateTime.now();
  }

  TimeOfDay _parseTime(String value) {
    try {
      final clean = value.replaceAll(RegExp(r'[APap][Mm]'), '').trim();
      final parts = clean.split(':');
      var hour = int.parse(parts[0]);
      final minute = parts.length > 1 ? int.parse(parts[1]) : 0;
      if (value.toUpperCase().contains('PM') && hour != 12) hour += 12;
      if (value.toUpperCase().contains('AM') && hour == 12) hour = 0;
      return TimeOfDay(hour: hour, minute: minute);
    } catch (_) {
      return const TimeOfDay(hour: 8, minute: 0);
    }
  }

  String _formatTime(TimeOfDay time) {
    return '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}:00';
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final assignmentId = widget.assignment['assignment_id']?.toString() ?? '';
    if (assignmentId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Assignment data is missing an ID.')),
      );
      return;
    }

    setState(() => _saving = true);
    final payload = {
      'region_id': widget.assignment['region_id']?.toString() ?? '',
      'supervisor_id': widget.supervisorId,
      'driver_id': _driverController.text.trim(),
      'vehicle_id': _vehicleController.text.trim(),
      'route_id': _routeController.text.trim(),
      'service_date': _serviceDate.toIso8601String().split('T')[0],
      'planned_start_time': _formatTime(_startTime),
      'planned_end_time': _formatTime(_endTime),
      'notes': _notesController.text.trim(),
    };
    debugPrint('EDIT_ASSIGNMENT_PAYLOAD: $payload');

    try {
      final uri = Uri.parse(
          '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/assignments/$assignmentId');
      final response = await http.put(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );
      if (!mounted) return;
      if (response.statusCode >= 200 && response.statusCode < 300) {
        widget.onSave();
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Assignment updated')),
        );
      } else {
        final body = response.body.isEmpty
            ? <String, dynamic>{}
            : jsonDecode(response.body) as Map<String, dynamic>;
        final detail =
            body['detail']?.toString() ?? 'Failed to update assignment';
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(detail)),
        );
      }
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error connecting to server: $error')),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Edit Assignment'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: _driverController,
                  decoration:
                      inputDecoration('Driver ID', Icons.person_outline),
                  validator: (value) => (value == null || value.trim().isEmpty)
                      ? 'Driver is required'
                      : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _vehicleController,
                  decoration:
                      inputDecoration('Vehicle ID', Icons.directions_bus),
                  validator: (value) => (value == null || value.trim().isEmpty)
                      ? 'Vehicle is required'
                      : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _routeController,
                  decoration: inputDecoration('Route ID', Icons.route_outlined),
                  validator: (value) => (value == null || value.trim().isEmpty)
                      ? 'Route is required'
                      : null,
                ),
                const SizedBox(height: 12),
                InkWell(
                  onTap: () async {
                    final date = await showDatePicker(
                      context: context,
                      initialDate: _serviceDate,
                      firstDate:
                          DateTime.now().subtract(const Duration(days: 30)),
                      lastDate: DateTime.now().add(const Duration(days: 365)),
                    );
                    if (date != null) setState(() => _serviceDate = date);
                  },
                  child: InputDecorator(
                    decoration:
                        inputDecoration('', Icons.calendar_today_outlined)
                            .copyWith(prefixIcon: null),
                    child: Text(_serviceDate.toIso8601String().split('T')[0]),
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: InkWell(
                        onTap: () async {
                          final time = await showTimePicker(
                              context: context, initialTime: _startTime);
                          if (time != null) setState(() => _startTime = time);
                        },
                        child: InputDecorator(
                          decoration: inputDecoration('', Icons.access_time)
                              .copyWith(prefixIcon: null),
                          child: Text('Start: ${_startTime.format(context)}'),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: InkWell(
                        onTap: () async {
                          final time = await showTimePicker(
                              context: context, initialTime: _endTime);
                          if (time != null) setState(() => _endTime = time);
                        },
                        child: InputDecorator(
                          decoration: inputDecoration('', Icons.access_time)
                              .copyWith(prefixIcon: null),
                          child: Text('End: ${_endTime.format(context)}'),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _notesController,
                  minLines: 3,
                  maxLines: 5,
                  decoration: inputDecoration('Notes', Icons.notes)
                      .copyWith(prefixIcon: null),
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _saving ? null : _save,
          style: filledStyle(orange),
          child: _saving
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(
                      strokeWidth: 2, color: Colors.white),
                )
              : const Text('Save'),
        ),
      ],
    );
  }
}

class AssignmentFormScreen extends StatefulWidget {
  const AssignmentFormScreen(
      {super.key,
      required this.supervisorId,
      this.assignment,
      required this.onSave});

  final String supervisorId;
  final Map<String, dynamic>? assignment;
  final VoidCallback onSave;

  @override
  State<AssignmentFormScreen> createState() => _AssignmentFormScreenState();
}

class _AssignmentFormScreenState extends State<AssignmentFormScreen> {
  final _formKey = GlobalKey<FormState>();

  // region is auto-loaded from the backend — no dropdown shown to the user
  String? _selectedRegion;
  String? _selectedDriver;
  String? _selectedVehicle;
  String? _selectedRoute;
  late DateTime _selectedDate;
  late TimeOfDay _startTime;
  late TimeOfDay _endTime;
  final _notesController = TextEditingController();

  List<String> _drivers = [];
  List<String> _vehicles = [];
  List<String> _routes = [];

  bool _loadingDrivers = true;
  String? _loadError;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    debugPrint("AUTH_SUPERVISOR_ID: ${widget.supervisorId}");
    _selectedDate = DateTime.now();
    _startTime = const TimeOfDay(hour: 8, minute: 0);
    _endTime = const TimeOfDay(hour: 10, minute: 0);

    if (widget.assignment != null) {
      final a = widget.assignment!;
      _selectedDriver = a['driver_id']?.toString();
      _selectedVehicle = a['vehicle_id']?.toString();
      _selectedRoute = a['route_id']?.toString();
      _selectedRegion = a['region_id']?.toString();
      _notesController.text = a['notes']?.toString() ?? '';

      try {
        if (a['service_date'] != null) {
          _selectedDate = DateTime.parse(a['service_date'].toString());
        }
      } catch (_) {}

      _startTime = _parseTime(a['start_time']?.toString() ??
          a['planned_start_time']?.toString() ??
          '08:00');
      _endTime = _parseTime(a['end_time']?.toString() ??
          a['planned_end_time']?.toString() ??
          '10:00');
    }

    _fetchInitialData();
  }

  TimeOfDay _parseTime(String timeStr) {
    try {
      final clean = timeStr.replaceAll(RegExp(r'[APap][Mm]'), '').trim();
      final parts = clean.split(':');
      int hr = int.parse(parts[0]);
      int min = parts.length > 1 ? int.parse(parts[1]) : 0;
      if (timeStr.toUpperCase().contains('PM') && hr != 12) {
        hr += 12;
      }
      if (timeStr.toUpperCase().contains('AM') && hr == 12) {
        hr = 0;
      }
      return TimeOfDay(hour: hr, minute: min);
    } catch (_) {
      return const TimeOfDay(hour: 8, minute: 0);
    }
  }

  Future<void> _fetchInitialData() async {
    debugPrint("LOAD_SUPERVISOR_REGION_START");
    try {
      // 1. If editing, use the existing assignment's region.
      //    Otherwise call GET /supervisor/{id}/region to auto-load the supervisor's region.
      if (widget.assignment != null && widget.assignment!['region_id'] != null) {
        _selectedRegion = widget.assignment!['region_id']?.toString();
        debugPrint("SELECTED_REGION_ID (from edit): $_selectedRegion");
        debugPrint("SUPERVISOR_REGION_RESPONSE: {\"region_id\": \"$_selectedRegion\", \"region_name\": \"$_selectedRegion\"}");
      } else {
        final resRegion = await http.get(Uri.parse(
            '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/region'));
        if (resRegion.statusCode == 200) {
          debugPrint("SUPERVISOR_REGION_RESPONSE: ${resRegion.body}");
          final data = jsonDecode(resRegion.body) as Map<String, dynamic>;
          _selectedRegion = data['region_id']?.toString();
        } else {
          // Fallback: still try the plural endpoint
          final resRegions = await http.get(Uri.parse(
              '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/regions'));
          if (resRegions.statusCode == 200) {
            final list = jsonDecode(resRegions.body) as List<dynamic>;
            if (list.isNotEmpty) {
              _selectedRegion = list.first['region_id']?.toString();
              debugPrint("SUPERVISOR_REGION_RESPONSE: {\"region_id\": \"$_selectedRegion\", \"region_name\": \"${list.first['region_name']}\"}");
            } else {
              final errMsg = 'Supervisor is not assigned to any region (status: ${resRegion.statusCode})';
              debugPrint("LOAD_SUPERVISOR_REGION_ERROR: $errMsg");
              throw Exception(errMsg);
            }
          } else {
            final errMsg = 'Failed to load supervisor region (status: ${resRegion.statusCode})';
            debugPrint("LOAD_SUPERVISOR_REGION_ERROR: $errMsg");
            throw Exception(errMsg);
          }
        }
        debugPrint("SELECTED_REGION_ID (auto-loaded): $_selectedRegion");
      }

      if (_selectedRegion == null || _selectedRegion!.isEmpty) {
        final errMsg = 'Supervisor is not assigned to an active region.';
        debugPrint("LOAD_SUPERVISOR_REGION_ERROR: $errMsg");
        throw Exception(errMsg);
      }

      // 2. Fetch routes & vehicles for the supervisor's region
      await _fetchRoutesAndVehicles(_selectedRegion);

      // 3. Fetch drivers owned by the supervisor's region.
      final encodedRegion = Uri.encodeComponent(_selectedRegion!);
      final encodedSupervisor = Uri.encodeComponent(widget.supervisorId);
      final driversUrl =
          '${ApiConfig.baseUrl}/regions/$encodedRegion/drivers?supervisor_id=$encodedSupervisor';
      debugPrint("DRIVERS_REQUEST_URL: $driversUrl");
      final resDrivers = await http.get(Uri.parse(driversUrl));
      if (resDrivers.statusCode == 200) {
        debugPrint("REGION_DRIVERS_RESPONSE: ${resDrivers.body}");
        final decoded = jsonDecode(resDrivers.body);
        final List<dynamic> data;
        if (decoded is Map && decoded.containsKey('drivers')) {
          data = decoded['drivers'] as List<dynamic>;
        } else if (decoded is List) {
          data = decoded;
        } else {
          data = [];
        }
        debugPrint("DRIVERS_PARSED_COUNT: ${data.length}");
        _drivers = data.map((d) => d['driver_id']?.toString() ?? '').where((id) => id.isNotEmpty).toList();
      } else {
        throw Exception('Failed to load region drivers (${resDrivers.statusCode})');
      }

      setState(() {
        if (_selectedDriver == null || !_drivers.contains(_selectedDriver)) {
          _selectedDriver = _drivers.isNotEmpty ? _drivers.first : null;
        }
        _loadError = null;
        _loadingDrivers = false;
      });
    } catch (e) {
      debugPrint("Error in _fetchInitialData: $e");
      final errClean = e.toString().replaceAll('Exception: ', '');
      if (_selectedRegion == null || _selectedRegion!.isEmpty) {
        debugPrint("LOAD_SUPERVISOR_REGION_ERROR: $errClean");
      }
      setState(() {
        _drivers = [];
        _routes = [];
        _vehicles = [];
        _selectedRoute = null;
        _selectedVehicle = null;
        _loadError = errClean;
        _selectedDriver = null;
        _loadingDrivers = false;
      });
    }
  }

  Future<void> _fetchRoutesAndVehicles(String? regionId) async {
    final encodedSupervisor = Uri.encodeComponent(widget.supervisorId);
    final encodedRegion = regionId == null ? null : Uri.encodeComponent(regionId);
    final routesUrl = encodedRegion != null
        ? '${ApiConfig.baseUrl}/regions/$encodedRegion/routes?supervisor_id=$encodedSupervisor'
        : '${ApiConfig.baseUrl}/supervisor/$encodedSupervisor/routes';
    final vehiclesUrl = encodedRegion != null
        ? '${ApiConfig.baseUrl}/regions/$encodedRegion/vehicles?supervisor_id=$encodedSupervisor'
        : '${ApiConfig.baseUrl}/supervisor/$encodedSupervisor/vehicles';
    
    debugPrint("SUPERVISOR_REGION_ID: $regionId");
    debugPrint("ROUTES_REQUEST_URL: $routesUrl");
    debugPrint("VEHICLES_REQUEST_URL: $vehiclesUrl");

    try {
      final resRoutes = await http.get(Uri.parse(routesUrl));
      debugPrint("ROUTES_RESPONSE_STATUS: ${resRoutes.statusCode} BODY: ${resRoutes.body}");
      if (resRoutes.statusCode == 200) {
        debugPrint("REGION_ROUTES_RESPONSE: ${resRoutes.body}");
        final data = jsonDecode(resRoutes.body) as List<dynamic>;
        _routes = data.map((r) => r['route_id']?.toString() ?? '').where((id) => id.isNotEmpty).toSet().toList();
        debugPrint("CREATE_ASSIGNMENT_ROUTE_OPTIONS: count=${_routes.length} routes=$_routes");
      } else {
        throw Exception('Failed to load region routes (${resRoutes.statusCode})');
      }

      final resVehicles = await http.get(Uri.parse(vehiclesUrl));
      debugPrint("VEHICLES_RESPONSE_STATUS: ${resVehicles.statusCode} BODY: ${resVehicles.body}");
      if (resVehicles.statusCode == 200) {
        debugPrint("REGION_VEHICLES_RESPONSE: ${resVehicles.body}");
        final data = jsonDecode(resVehicles.body) as List<dynamic>;
        _vehicles = data
            .map((v) {
              if (v is Map) return v['vehicle_id']?.toString() ?? '';
              return v.toString();
            })
            .where((id) => id.isNotEmpty)
            .toSet()
            .toList();
      } else {
        throw Exception('Failed to load region vehicles (${resVehicles.statusCode})');
      }

      setState(() {
        if (_selectedRoute == null || !_routes.contains(_selectedRoute)) {
          _selectedRoute = _routes.isNotEmpty ? _routes.first : null;
        }
        if (_selectedVehicle == null || !_vehicles.contains(_selectedVehicle)) {
          _selectedVehicle = _vehicles.isNotEmpty ? _vehicles.first : null;
        }
        _loadError = null;
        debugPrint("SELECTED_ROUTE_ID: $_selectedRoute");
        debugPrint("SELECTED_VEHICLE_ID: $_selectedVehicle");
      });
    } catch (e) {
      debugPrint("Error fetching routes/vehicles: $e");
      setState(() {
        _routes = [];
        _vehicles = [];
        _selectedRoute = null;
        _selectedVehicle = null;
        _loadError = e.toString().replaceAll('Exception: ', '');
      });
      rethrow;
    }
  }

  String _formatTime(TimeOfDay t) {
    final hr = t.hour.toString().padLeft(2, '0');
    final min = t.minute.toString().padLeft(2, '0');
    return '$hr:$min:00';
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    
    // Validations
    if (_selectedDriver == null || _selectedDriver!.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('driver_id is required')),
      );
      return;
    }
    if (_selectedVehicle == null || _selectedVehicle!.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('vehicle_id is required')),
      );
      return;
    }
    if (_selectedRoute == null || _selectedRoute!.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No bus routes assigned to your region. Contact Control Center.')),
      );
      return;
    }
    if (_selectedRegion == null || _selectedRegion!.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('region_id is required')),
      );
      return;
    }

    final serviceDateStr = _selectedDate.toIso8601String().split('T')[0];
    final startTimeStr = _formatTime(_startTime);
    final endTimeStr = _formatTime(_endTime);

    if (serviceDateStr.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('service_date is required')),
      );
      return;
    }
    if (startTimeStr.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('planned_start_time is required')),
      );
      return;
    }
    if (endTimeStr.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('planned_end_time is required')),
      );
      return;
    }

    // Time range validation
    final startMinutes = _startTime.hour * 60 + _startTime.minute;
    final endMinutes = _endTime.hour * 60 + _endTime.minute;
    if (startMinutes >= endMinutes) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Start time must be before end time')),
      );
      return;
    }

    setState(() => _saving = true);

    final isEdit = widget.assignment != null;

    final routeClean = _selectedRoute!.replaceAll(' ', '_');
    final driverClean = _selectedDriver!.replaceAll(' ', '_');
    final startTimeClean = startTimeStr.replaceAll(':', '');

    final tripId = isEdit
        ? (widget.assignment!['trip_id']?.toString() ?? 'OP_${routeClean}_${driverClean}_${serviceDateStr}_$startTimeClean')
        : 'OP_${routeClean}_${driverClean}_${serviceDateStr}_$startTimeClean';

    final status = isEdit
        ? (widget.assignment!['status']?.toString() ?? 'scheduled')
        : 'scheduled';

    final payload = {
      'region_id': _selectedRegion,
      'supervisor_id': widget.supervisorId,
      'driver_id': _selectedDriver,
      'vehicle_id': _selectedVehicle,
      'route_id': _selectedRoute,
      'trip_id': tripId,
      'service_date': serviceDateStr,
      'planned_start_time': startTimeStr,
      'planned_end_time': endTimeStr,
      'status': status,
      'notes': _notesController.text.trim(),
    };

    debugPrint('CREATE_ASSIGNMENT_PAYLOAD: ${jsonEncode(payload)}');
    debugPrint('  -> supervisor_id in URL will be: ${widget.supervisorId}');
    debugPrint('  -> region_id in body: ${_selectedRegion}');
    debugPrint('  -> route_id in body:  ${_selectedRoute}');
    debugPrint('  -> vehicle_id in body: ${_selectedVehicle}');
    debugPrint('  -> driver_id in body: ${_selectedDriver}');

    try {
      final isEdit = widget.assignment != null;
      final url = isEdit
          ? '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/assignments/${widget.assignment!['assignment_id']}'
          : '${ApiConfig.baseUrl}/supervisor/${widget.supervisorId}/assignments';

      debugPrint("POST_URL: $url");

      final response = isEdit
          ? await http.put(Uri.parse(url),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode(payload))
          : await http.post(Uri.parse(url),
              headers: {'Content-Type': 'application/json'},
              body: jsonEncode(payload));

      if (response.statusCode == 200 || response.statusCode == 201) {
        widget.onSave();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content:
                  Text(isEdit ? 'Assignment updated' : 'Assignment created')),
        );
        Navigator.pop(context);
      } else {
        debugPrint("ASSIGNMENT_ERROR_RESPONSE: status=${response.statusCode} body=${response.body}");
        String err = 'Failed to save assignment';
        try {
          err = jsonDecode(response.body)['detail']?.toString() ?? err;
        } catch (_) {
          err = response.body;
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $err')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error connecting to server: $e')),
      );
    } finally {
      setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.assignment != null;

    final bool hasNoRegion = _selectedRegion == null || _selectedRegion!.isEmpty;

    final List<String> disabledReasons = [];
    if (hasNoRegion) {
      disabledReasons.add("region_id is null or empty");
    }
    if (_selectedDriver == null || _selectedDriver!.isEmpty) {
      disabledReasons.add("driver_id is null or empty");
    }
    if (_selectedVehicle == null || _selectedVehicle!.isEmpty) {
      disabledReasons.add("vehicle_id is null or empty");
    }
    if (_selectedRoute == null || _selectedRoute!.isEmpty) {
      disabledReasons.add("route_id is null or empty");
    }
    if (_loadError != null && !hasNoRegion) {
      disabledReasons.add("load error active: $_loadError");
    }

    final bool isFormValid = disabledReasons.isEmpty;
    if (!isFormValid) {
      debugPrint("CREATE_ASSIGNMENT_FORM_DISABLED_REASON: ${disabledReasons.join(', ')}");
    }

    return Scaffold(
      appBar: simpleBar(
        context,
        title: isEdit ? 'Edit Assignment' : 'Create Assignment',
        subtitle: isEdit
            ? 'Update duty parameters'
            : 'Assign driver, vehicle, and route',
        color: orange,
      ),
      body: _loadingDrivers
          ? const Center(child: CircularProgressIndicator(color: orange))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // If supervisor has no active region, show one clean empty-state card at the top
                    if (hasNoRegion) ...[
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFF1F2),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: danger.withOpacity(.35)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: const [
                                Icon(Icons.error_outline, color: danger, size: 20),
                                SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    "No active region assigned",
                                    style: TextStyle(
                                      color: danger,
                                      fontWeight: FontWeight.w800,
                                      fontSize: 16,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            const Text(
                              "Please contact Control Center to assign you to a region before creating assignments.",
                              style: TextStyle(
                                color: Color(0xFF4B5563),
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 16),
                    ] else ...[
                      // Region is auto-loaded from the backend — no dropdown shown
                      if (_selectedRegion != null) ...[
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF4F6F8),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: const Color(0xFFD0D5DD)),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.map_outlined, size: 18, color: Color(0xFF6B7280)),
                              const SizedBox(width: 8),
                              Text(
                                'Region: ${_selectedRegion ?? ''}',
                                style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280)),
                              ),
                              const Spacer(),
                              const Icon(Icons.lock_outline, size: 16, color: Color(0xFF9CA3AF)),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],
                      if (_loadError != null) ...[
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFFF1F2),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: danger.withOpacity(.35)),
                          ),
                          child: Text(
                            "Error: $_loadError",
                            style: const TextStyle(
                              color: danger,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],
                    ],

                    FieldLabel(
                      label: 'Select Driver *',
                      child: DropdownButtonFormField<String>(
                        value: (_drivers.isEmpty || hasNoRegion) ? null : _selectedDriver,
                        decoration: inputDecoration('', Icons.person_outline)
                            .copyWith(prefixIcon: null),
                        items: (_drivers.isEmpty || hasNoRegion)
                            ? null
                            : _drivers
                                .map((d) =>
                                    DropdownMenuItem(value: d, child: Text(d)))
                                .toList(),
                        onChanged: (_drivers.isEmpty || hasNoRegion)
                            ? null
                            : (val) => setState(() => _selectedDriver = val),
                      ),
                    ),
                    if (_drivers.isEmpty && !hasNoRegion) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: const [
                          Expanded(
                            child: Text(
                              "No drivers assigned to this region.",
                              style: TextStyle(color: danger, fontSize: 12),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 16),

                    FieldLabel(
                      label: 'Select Vehicle *',
                      child: DropdownButtonFormField<String>(
                        value: (_vehicles.isEmpty || hasNoRegion) ? null : _selectedVehicle,
                        decoration: inputDecoration('', Icons.directions_bus)
                            .copyWith(prefixIcon: null),
                        items: (_vehicles.isEmpty || hasNoRegion)
                            ? null
                            : _vehicles
                                .map((v) =>
                                    DropdownMenuItem(value: v, child: Text(v)))
                                .toList(),
                        onChanged: (_vehicles.isEmpty || hasNoRegion)
                            ? null
                            : (val) {
                                setState(() {
                                  _selectedVehicle = val;
                                });
                                debugPrint("SELECTED_VEHICLE_ID: $val");
                              },
                      ),
                    ),
                    if (_vehicles.isEmpty && !hasNoRegion) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: const [
                          Expanded(
                            child: Text(
                              "No vehicles assigned to this region.",
                              style: TextStyle(color: danger, fontSize: 12),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 16),

                    FieldLabel(
                      label: 'Select Route *',
                      child: DropdownButtonFormField<String>(
                        value: (_routes.isEmpty || hasNoRegion) ? null : _selectedRoute,
                        decoration: inputDecoration('', Icons.route_outlined)
                            .copyWith(prefixIcon: null),
                        items: (_routes.isEmpty || hasNoRegion)
                            ? null
                            : _routes
                                .map((r) =>
                                    DropdownMenuItem(value: r, child: Text(r)))
                                .toList(),
                        onChanged: (_routes.isEmpty || hasNoRegion)
                            ? null
                            : (val) {
                                setState(() {
                                  _selectedRoute = val;
                                });
                                debugPrint("SELECTED_ROUTE_ID: $val");
                              },
                      ),
                    ),
                    if (_routes.isEmpty && !hasNoRegion) ...[
                      const SizedBox(height: 6),
                      Row(
                        children: const [
                          Expanded(
                            child: Text(
                              "No bus routes assigned to this region.",
                              style: TextStyle(color: danger, fontSize: 12),
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                    const SizedBox(height: 16),

                    FieldLabel(
                      label: 'Service Date *',
                      child: InkWell(
                        onTap: () async {
                          final date = await showDatePicker(
                            context: context,
                            initialDate: _selectedDate,
                            firstDate: DateTime.now()
                                .subtract(const Duration(days: 30)),
                            lastDate:
                                DateTime.now().add(const Duration(days: 365)),
                          );
                          if (date != null) {
                            setState(() => _selectedDate = date);
                          }
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 14),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF4F6F8),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: const Color(0xFFD0D5DD)),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                  _selectedDate.toIso8601String().split('T')[0],
                                  style: const TextStyle(fontSize: 16)),
                              const Icon(Icons.calendar_today_outlined,
                                  color: muted),
                            ],
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: FieldLabel(
                            label: 'Start Time *',
                            child: InkWell(
                              onTap: () async {
                                final time = await showTimePicker(
                                    context: context, initialTime: _startTime);
                                if (time != null) {
                                  setState(() => _startTime = time);
                                }
                              },
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 14, vertical: 14),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFF4F6F8),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                      color: const Color(0xFFD0D5DD)),
                                ),
                                child: Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(_startTime.format(context),
                                        style: const TextStyle(fontSize: 16)),
                                    const Icon(Icons.access_time, color: muted),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: FieldLabel(
                            label: 'End Time *',
                            child: InkWell(
                              onTap: () async {
                                final time = await showTimePicker(
                                    context: context, initialTime: _endTime);
                                if (time != null) {
                                  setState(() => _endTime = time);
                                }
                              },
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 14, vertical: 14),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFF4F6F8),
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(
                                      color: const Color(0xFFD0D5DD)),
                                ),
                                child: Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(_endTime.format(context),
                                        style: const TextStyle(fontSize: 16)),
                                    const Icon(Icons.access_time, color: muted),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    FieldLabel(
                      label: 'Notes / Instructions',
                      child: TextField(
                        controller: _notesController,
                        minLines: 3,
                        maxLines: 5,
                        decoration: inputDecoration(
                                'Add any specific instructions for the driver...',
                                Icons.notes)
                            .copyWith(prefixIcon: null),
                      ),
                    ),
                    const SizedBox(height: 32),
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: FilledButton(
                        onPressed: (_saving || !isFormValid) ? null : _save,
                        style: filledStyle(orange),
                        child: _saving
                            ? const CircularProgressIndicator(
                                color: Colors.white)
                            : Text(isFormValid
                                ? (isEdit ? 'Update Assignment' : 'Create Assignment')
                                : 'Complete region setup first.'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
    );
  }
}
