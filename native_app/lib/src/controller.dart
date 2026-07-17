import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'core_manager.dart';

class AiosController extends ChangeNotifier {
  AiosController({AiosApi? api, CoreManager? core}) : api = api ?? AiosApi() {
    this.core = core ?? CoreManager(api: this.api);
  }

  final AiosApi api;
  late final CoreManager core;
  static const _lifecycle = MethodChannel('aios/window_lifecycle');

  bool loading = true;
  bool syncing = false;
  bool darkMode = true;
  String message = 'Starting private AiOS Core...';
  String activePage = 'overview';
  Map<String, dynamic> live = const {};
  Map<String, dynamic> desktop = const {};
  Map<String, dynamic> accounts = const {};
  Map<String, dynamic> projects = const {};
  Map<String, dynamic> college = const {};
  final Map<String, Map<String, dynamic>> pageData = {};
  List<dynamic> workers = const [];
  bool pageLoading = false;
  Map<String, dynamic>? signIn;
  Timer? _refreshTimer;
  Timer? _signInTimer;

  Future<void> initialize() async {
    _lifecycle.setMethodCallHandler((call) async {
      if (call.method == 'exitRequested') {
        await exitApp();
      }
    });
    await _loadPreferences();
    try {
      await core.ensureRunning();
      await refresh();
      await refreshPageData(activePage, silent: true);
      _refreshTimer = Timer.periodic(
        const Duration(seconds: 12),
        (_) => unawaited(refresh(silent: true)),
      );
    } catch (error) {
      message = _friendly(error);
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> refreshPageData(String page, {bool silent = false}) async {
    final endpoint = _pageEndpoints[page];
    if (endpoint == null) return;
    if (!silent) {
      pageLoading = true;
      notifyListeners();
    }
    try {
      pageData[page] = await api.get(endpoint);
    } catch (error) {
      message = _friendly(error);
    } finally {
      pageLoading = false;
      notifyListeners();
    }
  }

  Map<String, dynamic> dataFor(String page) => pageData[page] ?? const {};

  Future<void> refresh({bool silent = false}) async {
    if (!silent) {
      loading = true;
      notifyListeners();
    }
    try {
      final values = await Future.wait([
        api.get('/api/live'),
        api.get('/api/desktop/status'),
        api.get('/api/intelligence/accounts'),
        api.get('/api/projects/context'),
        api.get('/api/college/pat'),
        api.get('/api/workers'),
      ]);
      live = values[0];
      desktop = values[1];
      accounts = values[2];
      projects = values[3];
      college = values[4];
      workers = values[5]['items'] as List<dynamic>? ?? const [];
      message = 'Private core connected at ${api.baseUrl}';
    } catch (error) {
      message = _friendly(error);
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> syncAll() async {
    if (syncing) return;
    syncing = true;
    message = 'Syncing Gmail and rebuilding local plans...';
    notifyListeners();
    try {
      final result = await api.post('/api/intelligence/sync');
      final analysis = result['analysis'] as Map<String, dynamic>? ?? const {};
      message =
          'Sync complete. ${analysis['analyzed'] ?? 0} messages analyzed locally.';
      await refresh(silent: true);
    } catch (error) {
      message = _friendly(error);
    } finally {
      syncing = false;
      notifyListeners();
    }
  }

  Future<void> connectGoogle() async {
    try {
      final result = await api.post(
        '/api/intelligence/accounts/google/connect',
      );
      signIn = result['sign_in'] as Map<String, dynamic>?;
      message = signIn?['message']?.toString() ?? 'Preparing Google sign-in...';
      notifyListeners();
      _signInTimer?.cancel();
      _signInTimer = Timer.periodic(
        const Duration(seconds: 1),
        (_) => unawaited(_pollSignIn()),
      );
    } catch (error) {
      message = _friendly(error);
      notifyListeners();
    }
  }

  Future<void> _pollSignIn() async {
    final id = signIn?['id']?.toString();
    if (id == null || id.isEmpty) return;
    try {
      final result = await api.get('/api/oauth/google/sign-in/$id');
      signIn = result['sign_in'] as Map<String, dynamic>?;
      message = signIn?['message']?.toString() ?? message;
      if (signIn?['terminal'] == true) {
        _signInTimer?.cancel();
        await refresh(silent: true);
      }
      notifyListeners();
    } catch (error) {
      message = _friendly(error);
      _signInTimer?.cancel();
      notifyListeners();
    }
  }

  Future<void> cancelGoogleSignIn() async {
    final id = signIn?['id']?.toString();
    if (id == null || id.isEmpty) return;
    await api.post('/api/oauth/google/sign-in/$id/cancel');
    _signInTimer?.cancel();
    signIn = null;
    message = 'Google sign-in cancelled.';
    notifyListeners();
  }

  Future<void> continueGoogleSignIn() async {
    final id = signIn?['id']?.toString();
    if (id == null || id.isEmpty) {
      await connectGoogle();
      return;
    }
    try {
      final result = await api.post('/api/oauth/google/sign-in/$id/continue');
      signIn = result['sign_in'] as Map<String, dynamic>? ?? signIn;
      message = signIn?['message']?.toString() ?? 'Continue in your browser.';
    } catch (error) {
      message = _friendly(error);
    }
    notifyListeners();
  }

  Future<void> syncAccount(int id) async {
    syncing = true;
    notifyListeners();
    try {
      final result = await api.post('/api/intelligence/accounts/$id/sync');
      message = result['message']?.toString() ?? 'Account synced.';
      await refresh(silent: true);
    } catch (error) {
      message = _friendly(error);
    } finally {
      syncing = false;
      notifyListeners();
    }
  }

  Future<void> removeAccount(int id) async {
    try {
      final result = await api.delete('/api/intelligence/accounts/$id');
      message = result['message']?.toString() ?? 'Account removed.';
      await refresh(silent: true);
    } catch (error) {
      message = _friendly(error);
      notifyListeners();
    }
  }

  Future<void> setStartup({
    required bool enabled,
    bool background = true,
  }) async {
    try {
      final result = await api.post('/api/desktop/startup', {
        'enabled': enabled,
        'background': background,
      });
      desktop = {...desktop, 'startup': result['startup']};
      message = enabled
          ? 'AiOS will start quietly when you sign in to Windows.'
          : 'Windows startup disabled.';
    } catch (error) {
      message = _friendly(error);
    }
    notifyListeners();
  }

  void selectPage(String page) {
    if (page == activePage) return;
    activePage = page;
    notifyListeners();
    unawaited(refreshPageData(page));
  }

  void toggleTheme() {
    darkMode = !darkMode;
    notifyListeners();
    unawaited(_savePreferences());
  }

  Future<void> hideToTray() => _lifecycle.invokeMethod('hideToTray');

  Future<void> exitApp() async {
    await core.stop();
    await _lifecycle.invokeMethod('exit');
  }

  Future<void> _loadPreferences() async {
    try {
      final data = jsonDecode(await _preferencesFile.readAsString());
      darkMode = data['darkMode'] != false;
    } catch (_) {}
  }

  Future<void> _savePreferences() async {
    await _preferencesFile.parent.create(recursive: true);
    await _preferencesFile.writeAsString(jsonEncode({'darkMode': darkMode}));
  }

  File get _preferencesFile {
    final root = Platform.environment['LOCALAPPDATA'] ?? Directory.current.path;
    return File('$root\\AiOS Assistant\\native-settings.json');
  }

  static const _pageEndpoints = <String, String>{
    'memory': '/api/memory',
    'planner': '/api/planner',
    'command-planner': '/api/planning-events',
    'automation': '/api/automation',
    'browser-agent': '/api/browser-agent',
    'career': '/api/career',
    'connectors': '/api/connectors',
    'notifications': '/api/notifications',
    'analytics': '/api/analytics',
  };

  String _friendly(Object error) => error.toString().replaceFirst(
    RegExp(r'^(Exception|StateError|FormatException): '),
    '',
  );

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _signInTimer?.cancel();
    super.dispose();
  }
}
