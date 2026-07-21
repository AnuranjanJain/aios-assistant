import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'core_manager.dart';

class AiosController extends ChangeNotifier {
  AiosController({
    AiosApi? api,
    CoreManager? core,
    File? preferencesFile,
    File? snapshotFile,
  }) : api = api ?? AiosApi(),
       _preferencesFileOverride = preferencesFile,
       _snapshotFileOverride = snapshotFile {
    this.core = core ?? CoreManager(api: this.api);
  }

  final AiosApi api;
  final File? _preferencesFileOverride;
  final File? _snapshotFileOverride;
  late final CoreManager core;
  static const _lifecycle = MethodChannel('aios/window_lifecycle');

  bool loading = true;
  bool syncing = false;
  bool memoryBusy = false;
  bool darkMode = true;
  String message = 'Starting private AiOS Core...';
  String activePage = 'overview';
  Map<String, dynamic> live = const {};
  Map<String, dynamic> desktop = const {};
  Map<String, dynamic> accounts = const {};
  final Map<String, Map<String, dynamic>> pageData = {};
  List<dynamic> workers = const [];
  bool pageLoading = false;
  final Set<String> busyActions = {};
  Map<String, dynamic>? signIn;
  Map<String, dynamic>? memoryAnswer;
  Timer? _refreshTimer;
  Timer? _startupRetryTimer;
  Timer? _signInTimer;
  Completer<void>? _refreshCompleter;

  Future<void> initialize() async {
    _lifecycle.setMethodCallHandler((call) async {
      if (call.method == 'exitRequested') {
        await exitApp();
      }
    });
    await _loadPreferences();
    final restoredSnapshot = await _loadSnapshot();
    if (restoredSnapshot) {
      loading = false;
      message = 'Showing saved local data while AiOS Core starts...';
      notifyListeners();
    }
    try {
      await core.ensureRunning();
      await refresh();
      await refreshPageData(activePage, silent: true);
    } catch (error) {
      final detail = _friendly(error);
      message = restoredSnapshot ? 'Showing saved local data. $detail' : detail;
    } finally {
      _refreshTimer ??= Timer.periodic(
        const Duration(seconds: 12),
        (_) => unawaited(refresh(silent: true)),
      );
      if (!api.connected) {
        _startupRetryTimer ??= Timer(
          const Duration(seconds: 3),
          () => unawaited(refresh(silent: true)),
        );
      }
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
      await _saveSnapshot();
    } catch (error) {
      message = _friendly(error);
    } finally {
      pageLoading = false;
      notifyListeners();
    }
  }

  Map<String, dynamic> dataFor(String page) => pageData[page] ?? const {};

  Future<void> refresh({bool silent = false}) async {
    final activeRefresh = _refreshCompleter;
    if (activeRefresh != null) {
      await activeRefresh.future;
      return;
    }
    final refreshCompleter = Completer<void>();
    _refreshCompleter = refreshCompleter;
    if (!silent) {
      loading = true;
      notifyListeners();
    }
    try {
      final values = await Future.wait([
        api.get('/api/live'),
        api.get('/api/desktop/status'),
        api.get('/api/intelligence/accounts'),
        api.get('/api/workers'),
      ]);
      live = values[0];
      desktop = values[1];
      accounts = values[2];
      workers = values[3]['items'] as List<dynamic>? ?? const [];
      message = 'Private core connected at ${api.baseUrl}';
      await _saveSnapshot();
    } catch (error) {
      message = _friendly(error);
    } finally {
      loading = false;
      refreshCompleter.complete();
      if (identical(_refreshCompleter, refreshCompleter)) {
        _refreshCompleter = null;
      }
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
      final views = result['views'] as Map<String, dynamic>? ?? const {};
      message =
          'Sync complete. ${views['emails_scanned'] ?? 0} recent emails from '
          '${views['accounts_scanned'] ?? 0} accounts; '
          '${analysis['analyzed'] ?? 0} analyzed locally.';
      await refresh(silent: true);
      await refreshPageData(activePage, silent: true);
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

  bool isActionBusy(String key) => busyActions.contains(key);

  Future<void> updateAccount(int id, {String? label, bool? syncEnabled}) async {
    final key = 'account:$id';
    if (isActionBusy(key)) return;
    busyActions.add(key);
    notifyListeners();
    try {
      final result = await api.patch('/api/intelligence/accounts/$id', {
        'label': ?label,
        'sync_enabled': ?syncEnabled,
      });
      message = result['message']?.toString() ?? 'Account updated.';
      await refresh(silent: true);
    } catch (error) {
      message = _friendly(error);
    } finally {
      busyActions.remove(key);
      notifyListeners();
    }
  }

  Future<void> updateReminder(int id, {required bool done}) async {
    final key = 'reminder:$id';
    if (isActionBusy(key)) return;
    busyActions.add(key);
    notifyListeners();
    try {
      final activeRefresh = _refreshCompleter;
      if (activeRefresh != null) await activeRefresh.future;
      final result = await api.post(
        '/api/reminders/$id/${done ? 'done' : 'read'}',
      );
      final updated = result['reminder'];
      if (updated is Map) {
        _applyReminderAction(
          Map<String, dynamic>.from(updated),
          completed: done,
        );
        await _saveSnapshot();
        notifyListeners();
      }
      message =
          result['message']?.toString() ??
          (done ? 'Reminder completed.' : 'Reminder marked as read.');
      await refreshPageData('reminders', silent: true);
      await refresh(silent: true);
    } catch (error) {
      message = _friendly(error);
    } finally {
      busyActions.remove(key);
      notifyListeners();
    }
  }

  void _applyReminderAction(
    Map<String, dynamic> updated, {
    required bool completed,
  }) {
    final id = (updated['id'] as num?)?.toInt();
    if (id == null) return;

    List<dynamic> updateItems(dynamic source) {
      final items = source is List ? List<dynamic>.from(source) : <dynamic>[];
      if (completed) {
        items.removeWhere((item) => item is Map && item['id'] == id);
        return items;
      }
      final index = items.indexWhere((item) => item is Map && item['id'] == id);
      if (index >= 0) {
        items[index] = updated;
      }
      return items;
    }

    final liveStats = _cachedMap(live['stats']);
    final liveItems = updateItems(live['reminders']);
    if (completed) {
      final active = (liveStats['active_reminders'] as num?)?.toInt();
      if (active != null) {
        liveStats['active_reminders'] = (active - 1).clamp(0, active);
      }
    }
    live = {...live, 'reminders': liveItems, 'stats': liveStats};

    final reminderPage = _cachedMap(pageData['reminders']);
    if (reminderPage.isNotEmpty) {
      final items = updateItems(reminderPage['items']);
      final stats = _cachedMap(reminderPage['stats']);
      stats['open'] = items.length;
      stats['unread'] = items
          .where((item) => item is Map && item['is_read'] != true)
          .length;
      stats['overdue'] = items
          .where((item) => item is Map && item['urgency'] == 'overdue')
          .length;
      stats['due_today'] = items
          .where((item) => item is Map && item['urgency'] == 'today')
          .length;
      if (completed) {
        stats['completed_today'] =
            ((stats['completed_today'] as num?)?.toInt() ?? 0) + 1;
      }
      pageData['reminders'] = {...reminderPage, 'items': items, 'stats': stats};
    }
  }

  Future<void> runConnector(String id) async {
    final key = 'connector:$id';
    if (isActionBusy(key)) return;
    busyActions.add(key);
    notifyListeners();
    try {
      final result = await api.post('/api/connectors/$id/run');
      message = result['message']?.toString() ?? 'Connector finished.';
      await refresh(silent: true);
      await refreshPageData('connectors', silent: true);
    } catch (error) {
      message = _friendly(error);
    } finally {
      busyActions.remove(key);
      notifyListeners();
    }
  }

  Future<void> setWorkerRunning(String id, {required bool running}) async {
    final key = 'worker:$id';
    if (isActionBusy(key)) return;
    busyActions.add(key);
    notifyListeners();
    try {
      final result = await api.post(
        '/api/workers/$id/${running ? 'start' : 'stop'}',
      );
      message =
          result['message']?.toString() ??
          (running ? 'Worker started.' : 'Worker stopped.');
      await refresh(silent: true);
    } catch (error) {
      message = _friendly(error);
    } finally {
      busyActions.remove(key);
      notifyListeners();
    }
  }

  Future<void> askMemory(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty || memoryBusy) return;
    memoryBusy = true;
    memoryAnswer = null;
    message = 'Searching your private memory...';
    notifyListeners();
    try {
      memoryAnswer = await api.post('/api/memory/ask', {'query': trimmed});
      message = 'Memory search complete.';
    } catch (error) {
      message = _friendly(error);
    } finally {
      memoryBusy = false;
      notifyListeners();
    }
  }

  Future<bool> createMemoryEntity({
    required String entityType,
    required String name,
    required String status,
    required String summary,
  }) => _saveMemory('/api/memory/entities', {
    'entity_type': entityType,
    'name': name,
    'status': status,
    'summary': summary,
  }, 'Memory entity saved.');

  Future<bool> saveMemoryNote({
    required String entityName,
    required String entityType,
    required String content,
  }) => _saveMemory('/api/memory/facts', {
    if (entityName.trim().isNotEmpty) 'entity_name': entityName.trim(),
    'entity_type': entityType,
    'content': content,
    'fact_type': 'note',
    'source': 'native AiOS memory',
  }, 'Memory note saved locally.');

  Future<bool> saveMemoryCheckpoint({
    required String projectName,
    required String summary,
    required String openFiles,
    required String activeTasks,
    required String nextActions,
    required String notes,
  }) => _saveMemory('/api/memory/checkpoints', {
    'project_name': projectName,
    'summary': summary,
    'open_files': openFiles,
    'active_tasks': activeTasks,
    'next_actions': nextActions,
    'notes': notes,
    'source': 'native AiOS memory',
  }, 'Project checkpoint saved.');

  Future<bool> _saveMemory(
    String path,
    Map<String, dynamic> body,
    String successMessage,
  ) async {
    if (memoryBusy) return false;
    memoryBusy = true;
    notifyListeners();
    try {
      await api.post(path, body);
      await refreshPageData('memory', silent: true);
      message = successMessage;
      return true;
    } catch (error) {
      message = _friendly(error);
      return false;
    } finally {
      memoryBusy = false;
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

  Future<bool> _loadSnapshot() async {
    try {
      final decoded = jsonDecode(await _snapshotFile.readAsString());
      if (decoded is! Map) return false;
      live = _cachedMap(decoded['live']);
      desktop = _cachedMap(decoded['desktop']);
      accounts = _cachedMap(decoded['accounts']);
      final cachedWorkers = decoded['workers'];
      workers = cachedWorkers is List
          ? List<dynamic>.from(cachedWorkers)
          : const [];
      final cachedPages = decoded['pageData'];
      if (cachedPages is Map) {
        for (final entry in cachedPages.entries) {
          pageData[entry.key.toString()] = _cachedMap(entry.value);
        }
      }
      return live.isNotEmpty || accounts.isNotEmpty || pageData.isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<void> _saveSnapshot() async {
    try {
      await _snapshotFile.parent.create(recursive: true);
      await _snapshotFile.writeAsString(
        jsonEncode({
          'version': 1,
          'updatedAt': DateTime.now().toUtc().toIso8601String(),
          'live': live,
          'desktop': desktop,
          'accounts': accounts,
          'workers': workers,
          'pageData': pageData,
        }),
        flush: true,
      );
    } catch (_) {
      // The live API remains authoritative if the optional view cache fails.
    }
  }

  static Map<String, dynamic> _cachedMap(dynamic value) => value is Map
      ? Map<String, dynamic>.fromEntries(
          value.entries.map(
            (entry) => MapEntry(entry.key.toString(), entry.value),
          ),
        )
      : <String, dynamic>{};

  File get _preferencesFile {
    if (_preferencesFileOverride != null) return _preferencesFileOverride;
    final root = Platform.environment['LOCALAPPDATA'] ?? Directory.current.path;
    return File('$root\\AiOS Assistant\\native-settings.json');
  }

  File get _snapshotFile {
    if (_snapshotFileOverride != null) return _snapshotFileOverride;
    final root = Platform.environment['LOCALAPPDATA'] ?? Directory.current.path;
    return File('$root\\AiOS Assistant\\native-view-cache.json');
  }

  static const _pageEndpoints = <String, String>{
    'opportunities': '/api/opportunities/overview',
    'reminders': '/api/reminders/overview',
    'memory': '/api/memory',
    'connectors': '/api/connectors',
  };

  String _friendly(Object error) => error.toString().replaceFirst(
    RegExp(r'^(Exception|StateError|FormatException): '),
    '',
  );

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _startupRetryTimer?.cancel();
    _signInTimer?.cancel();
    super.dispose();
  }
}
