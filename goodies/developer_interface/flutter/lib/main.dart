import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

void main() => runApp(const WebSweeperDeveloperApp());

class WebSweeperDeveloperApp extends StatefulWidget {
  const WebSweeperDeveloperApp({super.key});

  @override
  State<WebSweeperDeveloperApp> createState() => _WebSweeperDeveloperAppState();
}

class _WebSweeperDeveloperAppState extends State<WebSweeperDeveloperApp> {
  static const _defaultText = Color(0xffedf7ef);
  Color _textColor = _defaultText;

  @override
  void initState() {
    super.initState();
    _restoreColor();
  }

  Future<void> _restoreColor() async {
    final preferences = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      _textColor = Color(
        preferences.getInt('interface_text_color') ?? _defaultText.toARGB32(),
      );
    });
  }

  Future<void> _setTextColor(Color color) async {
    setState(() => _textColor = color);
    final preferences = await SharedPreferences.getInstance();
    await preferences.setInt('interface_text_color', color.toARGB32());
  }

  @override
  Widget build(BuildContext context) {
    final base = ThemeData.dark(useMaterial3: true);
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Web Sweeper Developer Interface',
      theme: base.copyWith(
        scaffoldBackgroundColor: const Color(0xff07110d),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xff35d07f),
          brightness: Brightness.dark,
        ),
        textTheme: base.textTheme.apply(
          bodyColor: _textColor,
          displayColor: _textColor,
        ),
        appBarTheme: AppBarTheme(
          backgroundColor: const Color(0xff0b1913),
          foregroundColor: _textColor,
          elevation: 0,
        ),
        inputDecorationTheme: const InputDecorationTheme(
          filled: true,
          fillColor: Color(0xff10251b),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
          ),
        ),
        cardTheme: const CardThemeData(
          color: Color(0xff0d1d16),
          margin: EdgeInsets.zero,
          elevation: 0,
          shape: RoundedRectangleBorder(
            side: BorderSide(color: Color(0xff1e4733)),
            borderRadius: BorderRadius.all(Radius.circular(18)),
          ),
        ),
      ),
      home: DeveloperDashboard(
        textColor: _textColor,
        onTextColorChanged: _setTextColor,
      ),
    );
  }
}

class DeveloperDashboard extends StatefulWidget {
  const DeveloperDashboard({
    super.key,
    required this.textColor,
    required this.onTextColorChanged,
  });

  final Color textColor;
  final ValueChanged<Color> onTextColorChanged;

  @override
  State<DeveloperDashboard> createState() => _DeveloperDashboardState();
}

class _DeveloperDashboardState extends State<DeveloperDashboard> {
  int _sourceSlots = 2;
  int _batchTarget = 2000;
  int _uploadTarget = 100;
  String _selectedModel = 'Open Library';
  bool _tertiary = true;
  bool _bridge = false;
  bool _connecting = false;
  int _codexLive = 26549;
  String _endpoint = 'http://127.0.0.1:8790';
  String _token = '';
  String _connectionMessage = 'Local controller not connected';

  List<ModelView> _models = const [
    ModelView(
      id: 'open-library',
      name: 'Open Library',
      stage: 'Acquiring',
      accepted: 1462,
      target: 2000,
      uploaded: 0,
      health: Health.healthy,
      detail: 'Checkpoint advancing · two workers',
    ),
    ModelView(
      id: 'library-of-congress',
      name: 'Library of Congress',
      stage: 'Staging upload',
      accepted: 1988,
      target: 2000,
      uploaded: 1725,
      health: Health.watch,
      detail: 'Receipt-bound upload in progress',
    ),
    ModelView(
      id: 'publisher',
      name: 'Stage-to-live publisher',
      stage: 'Live verification',
      accepted: 1486,
      target: 1486,
      uploaded: 1486,
      health: Health.healthy,
      detail: 'Single serialized writer · 1 GiB gate',
    ),
  ];

  @override
  void initState() {
    super.initState();
    _restoreConnection();
  }

  Future<void> _restoreConnection() async {
    final preferences = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      _endpoint = preferences.getString('controller_endpoint') ?? _endpoint;
      _token = preferences.getString('controller_token') ?? '';
    });
  }

  Future<void> _connect() async {
    setState(() {
      _connecting = true;
      _connectionMessage = 'Connecting…';
    });
    try {
      final base = _endpoint.endsWith('/')
          ? _endpoint.substring(0, _endpoint.length - 1)
          : _endpoint;
      final response = await http
          .get(
            Uri.parse('$base/api/status'),
            headers: _token.isEmpty ? {} : {'Authorization': 'Bearer $_token'},
          )
          .timeout(const Duration(seconds: 8));
      if (response.statusCode != 200) {
        throw Exception('controller returned ${response.statusCode}');
      }
      final payload = jsonDecode(response.body) as Map<String, dynamic>;
      final preferences = await SharedPreferences.getInstance();
      await preferences.setString('controller_endpoint', _endpoint);
      await preferences.setString('controller_token', _token);
      final lanes = payload['lanes'];
      if (!mounted) return;
      setState(() {
        _codexLive = (payload['codexLive'] as num?)?.toInt() ?? _codexLive;
        if (lanes is List) {
          _models = lanes
              .whereType<Map>()
              .map((raw) => ModelView.fromJson(Map<String, dynamic>.from(raw)))
              .toList();
          if (_models.isNotEmpty &&
              !_models.any((model) => model.name == _selectedModel)) {
            _selectedModel = _models.first.name;
          }
        }
        _connectionMessage = 'Connected · live controller data';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _connectionMessage = 'Connection failed · $error');
    } finally {
      if (mounted) setState(() => _connecting = false);
    }
  }

  Future<void> _sendAction(String action) async {
    if (_models.isEmpty) {
      _notice('No configured lane is available');
      return;
    }
    final selected = _models.firstWhere(
      (model) => model.name == _selectedModel,
      orElse: () => _models.first,
    );
    try {
      final base = _endpoint.endsWith('/')
          ? _endpoint.substring(0, _endpoint.length - 1)
          : _endpoint;
      final response = await http
          .post(
            Uri.parse('$base/api/action'),
            headers: {
              'Content-Type': 'application/json',
              if (_token.isNotEmpty) 'Authorization': 'Bearer $_token',
            },
            body: jsonEncode({'action': action, 'lane': selected.id}),
          )
          .timeout(const Duration(seconds: 8));
      if (!mounted) return;
      if (response.statusCode == 202 || response.statusCode == 200) {
        _notice(
          '${action[0].toUpperCase()}${action.substring(1)} request accepted for ${selected.name}',
        );
      } else {
        _notice(
          'Request not accepted · controller returned ${response.statusCode}',
        );
      }
    } catch (error) {
      if (mounted) _notice('Request failed · $error');
    }
  }

  void _notice(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 72,
        titleSpacing: 14,
        title: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.asset(
                'assets/sweeper-logo.png',
                width: 50,
                height: 50,
                fit: BoxFit.cover,
              ),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    'WEB SWEEPER',
                    maxLines: 1,
                    overflow: TextOverflow.fade,
                    softWrap: false,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.1,
                    ),
                  ),
                  Text(
                    'Developer Interface',
                    maxLines: 1,
                    overflow: TextOverflow.fade,
                    softWrap: false,
                    style: TextStyle(fontSize: 12, color: Color(0xff83cda4)),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Refresh status',
            onPressed: () => _notice('Status refreshed'),
            icon: const Icon(Icons.refresh_rounded),
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1500),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _topArea(),
                  const SizedBox(height: 16),
                  _sectionTitle(
                    'Operating lanes',
                    'Live status, progress, and current stage',
                  ),
                  const SizedBox(height: 10),
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final columns = constraints.maxWidth >= 1050
                          ? 3
                          : constraints.maxWidth >= 660
                          ? 2
                          : 1;
                      final width =
                          (constraints.maxWidth - (columns - 1) * 12) / columns;
                      return Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: _models
                            .map(
                              (model) => SizedBox(
                                width: width,
                                child: ModelCard(model: model),
                              ),
                            )
                            .toList(),
                      );
                    },
                  ),
                  const SizedBox(height: 18),
                  _controls(),
                  const SizedBox(height: 18),
                  _activityLog(),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _topArea() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final summary = Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'SYSTEM OVERVIEW',
              style: TextStyle(
                color: Color(0xff64dc98),
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                Metric(
                  label: 'Codex Live',
                  value: _codexLive.toString(),
                  icon: Icons.public_rounded,
                ),
                const Metric(
                  label: 'Confirmed staged',
                  value: '31,882',
                  icon: Icons.inventory_2_outlined,
                ),
                Metric(
                  label: 'Uploading now',
                  value: '1,725',
                  icon: Icons.cloud_upload_outlined,
                ),
                Metric(
                  label: 'Healthy lanes',
                  value: '3 / 3',
                  icon: Icons.health_and_safety_outlined,
                ),
              ],
            ),
            const SizedBox(height: 12),
            const Card(
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.verified_user_outlined,
                      color: Color(0xff64dc98),
                    ),
                    SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Production remains protected by one serialized writer, exact duplicate screening, and live verification.',
                        softWrap: true,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );

        if (constraints.maxWidth >= 980) {
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: summary),
              const SizedBox(width: 16),
              const SizedBox(width: 330, child: MemoryWaitingGame()),
            ],
          );
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            summary,
            const SizedBox(height: 14),
            const MemoryWaitingGame(),
          ],
        );
      },
    );
  }

  Widget _controls() {
    const colors = [
      Color(0xffedf7ef),
      Color(0xffffffff),
      Color(0xffb9f7d2),
      Color(0xffffe8a3),
      Color(0xffb8dcff),
      Color(0xffffc7df),
    ];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _sectionTitle(
              'Controls',
              'Set source lanes, batch sizes, uploader allowance, and manual recovery',
            ),
            const SizedBox(height: 14),
            _connectionPanel(),
            const SizedBox(height: 14),
            LayoutBuilder(
              builder: (context, constraints) {
                final fieldWidth = constraints.maxWidth >= 900
                    ? (constraints.maxWidth - 36) / 4
                    : constraints.maxWidth >= 540
                    ? (constraints.maxWidth - 12) / 2
                    : constraints.maxWidth;
                return Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    SizedBox(width: fieldWidth, child: _dropdown()),
                    SizedBox(
                      width: fieldWidth,
                      child: _numberField(
                        'Source slots (1–10)',
                        _sourceSlots,
                        (v) => setState(() => _sourceSlots = v.clamp(1, 10)),
                      ),
                    ),
                    SizedBox(
                      width: fieldWidth,
                      child: _numberField(
                        'Batch target',
                        _batchTarget,
                        (v) =>
                            setState(() => _batchTarget = v.clamp(1, 100000)),
                      ),
                    ),
                    SizedBox(
                      width: fieldWidth,
                      child: _numberField(
                        'Upload unit',
                        _uploadTarget,
                        (v) =>
                            setState(() => _uploadTarget = v.clamp(1, 100000)),
                      ),
                    ),
                  ],
                );
              },
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                const Text(
                  'Readable text color:',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                for (final color in colors)
                  Semantics(
                    label:
                        'Choose text color ${color.toARGB32().toRadixString(16)}',
                    button: true,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(20),
                      onTap: () => widget.onTextColorChanged(color),
                      child: Container(
                        width: 34,
                        height: 34,
                        decoration: BoxDecoration(
                          color: color,
                          shape: BoxShape.circle,
                          border: Border.all(
                            color:
                                widget.textColor.toARGB32() == color.toARGB32()
                                ? const Color(0xff35d07f)
                                : Colors.white24,
                            width:
                                widget.textColor.toARGB32() == color.toARGB32()
                                ? 3
                                : 1,
                          ),
                        ),
                        child: widget.textColor.toARGB32() == color.toARGB32()
                            ? const Icon(
                                Icons.check,
                                color: Colors.black,
                                size: 18,
                              )
                            : null,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilterChip(
                  selected: _tertiary,
                  label: const Text('Tertiary signals'),
                  onSelected: (value) => setState(() => _tertiary = value),
                ),
                FilterChip(
                  selected: _bridge,
                  label: const Text('Bridge switch'),
                  onSelected: (value) => setState(() => _bridge = value),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                FilledButton.icon(
                  onPressed: () => _notice('Configuration loaded'),
                  icon: const Icon(Icons.folder_open_outlined),
                  label: const Text('Load'),
                ),
                FilledButton.tonalIcon(
                  onPressed: () => _sendAction('switch'),
                  icon: const Icon(Icons.swap_horiz_rounded),
                  label: const Text('Switch'),
                ),
                FilledButton.tonalIcon(
                  onPressed: () => _sendAction('bridge'),
                  icon: const Icon(Icons.route_outlined),
                  label: const Text('Bridge'),
                ),
                OutlinedButton.icon(
                  onPressed: () => _sendAction('reset'),
                  icon: const Icon(Icons.restart_alt_rounded),
                  label: const Text('Reset model'),
                ),
                OutlinedButton.icon(
                  onPressed: () => _sendAction('upload'),
                  icon: const Icon(Icons.publish_outlined),
                  label: const Text('Upload'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _dropdown() => DropdownButtonFormField<String>(
    initialValue: _selectedModel,
    isExpanded: true,
    decoration: const InputDecoration(labelText: 'Selected model'),
    items: _models
        .map(
          (m) => DropdownMenuItem(
            value: m.name,
            child: Text(m.name, overflow: TextOverflow.ellipsis),
          ),
        )
        .toList(),
    onChanged: (value) =>
        setState(() => _selectedModel = value ?? _selectedModel),
  );

  Widget _connectionPanel() => Container(
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: const Color(0xff0a1711),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xff1e4733)),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text(
          'CONTROLLER CONNECTION',
          style: TextStyle(
            color: Color(0xff64dc98),
            fontWeight: FontWeight.w800,
            fontSize: 12,
          ),
        ),
        const SizedBox(height: 9),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 720;
            final endpoint = TextFormField(
              key: ValueKey('endpoint-$_endpoint'),
              initialValue: _endpoint,
              decoration: const InputDecoration(
                labelText: 'Controller URL',
                hintText: 'https://sweeper.example.org',
              ),
              keyboardType: TextInputType.url,
              onChanged: (value) => _endpoint = value.trim(),
            );
            final token = TextFormField(
              key: ValueKey('token-${_token.length}'),
              initialValue: _token,
              obscureText: true,
              enableSuggestions: false,
              autocorrect: false,
              decoration: const InputDecoration(labelText: 'Access token'),
              onChanged: (value) => _token = value,
            );
            if (compact) {
              return Column(
                children: [endpoint, const SizedBox(height: 10), token],
              );
            }
            return Row(
              children: [
                Expanded(flex: 3, child: endpoint),
                const SizedBox(width: 10),
                Expanded(flex: 2, child: token),
              ],
            );
          },
        ),
        const SizedBox(height: 9),
        Wrap(
          spacing: 10,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            FilledButton.tonalIcon(
              onPressed: _connecting ? null : _connect,
              icon: _connecting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.link_rounded),
              label: const Text('Connect'),
            ),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Text(
                _connectionMessage,
                softWrap: true,
                style: const TextStyle(fontSize: 12, color: Color(0xff83a891)),
              ),
            ),
          ],
        ),
        const SizedBox(height: 7),
        const Text(
          'Phones require a reachable HTTPS endpoint. Credentials stay on this device and are never included in public source.',
          softWrap: true,
          style: TextStyle(fontSize: 11, color: Color(0xff83a891)),
        ),
      ],
    ),
  );

  Widget _numberField(String label, int value, ValueChanged<int> changed) {
    return TextFormField(
      key: ValueKey('$label-$value'),
      initialValue: '$value',
      keyboardType: TextInputType.number,
      decoration: InputDecoration(labelText: label),
      onChanged: (text) {
        final parsed = int.tryParse(text);
        if (parsed != null) changed(parsed);
      },
    );
  }

  Widget _activityLog() => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _sectionTitle('Activity', 'Most recent recorded messages'),
          const SizedBox(height: 10),
          const LogRow(
            time: 'Now',
            text: 'All three lanes are healthy',
            color: Color(0xff35d07f),
          ),
          const LogRow(
            time: '2m',
            text: 'LOC staging receipt advanced',
            color: Color(0xfff5c451),
          ),
          const LogRow(
            time: '5m',
            text: 'Publisher completed fresh live duplicate delta',
            color: Color(0xff35d07f),
          ),
        ],
      ),
    ),
  );

  Widget _sectionTitle(String title, String subtitle) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        title,
        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 2),
      Text(
        subtitle,
        softWrap: true,
        style: const TextStyle(fontSize: 12, color: Color(0xff83a891)),
      ),
    ],
  );
}

enum Health { healthy, watch, stuck, failed }

class ModelView {
  const ModelView({
    required this.id,
    required this.name,
    required this.stage,
    required this.accepted,
    required this.target,
    required this.uploaded,
    required this.health,
    required this.detail,
  });
  final String id;
  final String name;
  final String stage;
  final int accepted;
  final int target;
  final int uploaded;
  final Health health;
  final String detail;

  factory ModelView.fromJson(Map<String, dynamic> json) {
    final healthName = (json['health'] as String? ?? 'watch').toLowerCase();
    return ModelView(
      id: json['id'] as String? ?? 'unnamed-lane',
      name: json['name'] as String? ?? 'Unnamed lane',
      stage: json['stage'] as String? ?? 'unknown',
      accepted: (json['accepted'] as num?)?.toInt() ?? 0,
      target: (json['target'] as num?)?.toInt() ?? 0,
      uploaded: (json['uploaded'] as num?)?.toInt() ?? 0,
      health: Health.values.firstWhere(
        (value) => value.name == healthName,
        orElse: () => Health.watch,
      ),
      detail: json['detail'] as String? ?? 'No current detail',
    );
  }
}

class ModelCard extends StatelessWidget {
  const ModelCard({super.key, required this.model});
  final ModelView model;

  Color get color => switch (model.health) {
    Health.healthy => const Color(0xff35d07f),
    Health.watch => const Color(0xfff5d142),
    Health.stuck => const Color(0xffff8a3d),
    Health.failed => const Color(0xffff4e5b),
  };

  @override
  Widget build(BuildContext context) {
    final progress = model.target == 0
        ? 0.0
        : (model.accepted / model.target).clamp(0.0, 1.0);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(15),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 10,
                  height: 10,
                  margin: const EdgeInsets.only(top: 5),
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    model.name,
                    softWrap: true,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 15,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    model.stage,
                    textAlign: TextAlign.end,
                    softWrap: true,
                    style: TextStyle(
                      fontSize: 11,
                      color: color,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              '${model.accepted.toString()} / ${model.target.toString()}',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 7),
            LinearProgressIndicator(
              value: progress,
              minHeight: 7,
              borderRadius: BorderRadius.circular(8),
              backgroundColor: const Color(0xff173426),
              color: color,
            ),
            const SizedBox(height: 9),
            Text(
              '${(progress * 100).toStringAsFixed(1)}% · ${model.uploaded} uploaded',
              softWrap: true,
            ),
            const SizedBox(height: 5),
            Text(
              model.detail,
              softWrap: true,
              style: const TextStyle(fontSize: 12, color: Color(0xff83a891)),
            ),
          ],
        ),
      ),
    );
  }
}

class Metric extends StatelessWidget {
  const Metric({
    super.key,
    required this.label,
    required this.value,
    required this.icon,
  });
  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Container(
    constraints: const BoxConstraints(minWidth: 138),
    padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 11),
    decoration: BoxDecoration(
      color: const Color(0xff0d1d16),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xff1e4733)),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 19, color: const Color(0xff64dc98)),
        const SizedBox(width: 8),
        Flexible(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                value,
                maxLines: 1,
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 16,
                ),
              ),
              Text(
                label,
                softWrap: true,
                style: const TextStyle(fontSize: 10, color: Color(0xff83a891)),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class LogRow extends StatelessWidget {
  const LogRow({
    super.key,
    required this.time,
    required this.text,
    required this.color,
  });
  final String time;
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 38,
          child: Text(
            time,
            style: const TextStyle(fontSize: 11, color: Color(0xff83a891)),
          ),
        ),
        Container(
          width: 7,
          height: 7,
          margin: const EdgeInsets.only(top: 5),
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 9),
        Expanded(child: Text(text, softWrap: true)),
      ],
    ),
  );
}

class MemoryWaitingGame extends StatefulWidget {
  const MemoryWaitingGame({super.key});

  @override
  State<MemoryWaitingGame> createState() => _MemoryWaitingGameState();
}

class _MemoryWaitingGameState extends State<MemoryWaitingGame> {
  final _random = Random();
  final List<int> _sequence = [];
  final List<int> _entered = [];
  int? _litPad;
  int _score = 0;
  int _highScore = 0;
  bool _playingSequence = false;
  bool _milestoneShown = false;
  String _message = 'Press Start, watch the pads, then repeat.';

  @override
  void initState() {
    super.initState();
    _restoreGame();
  }

  Future<void> _restoreGame() async {
    final preferences = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      _highScore = preferences.getInt('waiting_game_high_score') ?? 0;
      _milestoneShown =
          preferences.getBool('waiting_game_milestone_20') ?? false;
    });
  }

  Future<void> _start() async {
    if (_playingSequence) return;
    setState(() {
      _sequence.clear();
      _entered.clear();
      _score = 0;
      _message = 'Watch…';
    });
    await _nextRound();
  }

  Future<void> _nextRound() async {
    _sequence.add(_random.nextInt(4) + 1);
    _entered.clear();
    setState(() {
      _playingSequence = true;
      _message =
          'Watch ${_sequence.length} ${_sequence.length == 1 ? 'number' : 'numbers'}…';
    });
    await Future<void>.delayed(const Duration(milliseconds: 450));
    for (final pad in _sequence) {
      if (!mounted) return;
      setState(() => _litPad = pad);
      await Future<void>.delayed(const Duration(milliseconds: 360));
      if (!mounted) return;
      setState(() => _litPad = null);
      await Future<void>.delayed(const Duration(milliseconds: 160));
    }
    if (!mounted) return;
    setState(() {
      _playingSequence = false;
      _message = 'Your turn';
    });
  }

  Future<void> _tap(int pad) async {
    if (_playingSequence || _sequence.isEmpty) return;
    final expected = _sequence[_entered.length];
    setState(() {
      _litPad = pad;
      _entered.add(pad);
    });
    Timer(const Duration(milliseconds: 160), () {
      if (mounted && _litPad == pad) setState(() => _litPad = null);
    });
    if (pad != expected) {
      setState(() => _message = 'Not quite. Press Start to try again.');
      return;
    }
    if (_entered.length != _sequence.length) return;

    _score += 1;
    if (_score > _highScore) {
      _highScore = _score;
      final preferences = await SharedPreferences.getInstance();
      await preferences.setInt('waiting_game_high_score', _highScore);
    }
    if (_score >= 20 && !_milestoneShown && mounted) {
      _milestoneShown = true;
      final preferences = await SharedPreferences.getInstance();
      await preferences.setBool('waiting_game_milestone_20', true);
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Chris was innocent.')));
    }
    if (!mounted) return;
    setState(() => _message = 'Correct! Round ${_score + 1}');
    await Future<void>.delayed(const Duration(milliseconds: 450));
    if (mounted) await _nextRound();
  }

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(15),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'WAITING GAME',
                      style: TextStyle(
                        fontWeight: FontWeight.w900,
                        color: Color(0xff64dc98),
                      ),
                    ),
                    Text(
                      'Repeat the four-pad sequence',
                      softWrap: true,
                      style: TextStyle(fontSize: 11, color: Color(0xff83a891)),
                    ),
                  ],
                ),
              ),
              Text(
                '$_score · BEST $_highScore',
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            _message,
            textAlign: TextAlign.center,
            softWrap: true,
            style: const TextStyle(fontSize: 12),
          ),
          const SizedBox(height: 10),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            childAspectRatio: 2.05,
            children: [for (var pad = 1; pad <= 4; pad++) _pad(pad)],
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: _playingSequence ? null : _start,
            icon: const Icon(Icons.play_arrow_rounded),
            label: Text(_sequence.isEmpty ? 'Start' : 'Restart'),
          ),
        ],
      ),
    ),
  );

  Widget _pad(int pad) {
    final lit = _litPad == pad;
    return Semantics(
      key: ValueKey('memory-pad-$pad'),
      button: true,
      label: 'Memory pad $pad',
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => _tap(pad),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 100),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: lit ? const Color(0xff63f5a4) : const Color(0xff173c2a),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: lit ? Colors.white : const Color(0xff2e6c4c),
              width: lit ? 2 : 1,
            ),
            boxShadow: lit
                ? const [BoxShadow(color: Color(0x9935d07f), blurRadius: 16)]
                : null,
          ),
          child: Text(
            '$pad',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w900,
              color: lit ? const Color(0xff052516) : null,
            ),
          ),
        ),
      ),
    );
  }
}
