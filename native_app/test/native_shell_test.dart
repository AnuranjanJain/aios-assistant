import 'dart:io';

import 'package:aios_assistant/src/api.dart';
import 'package:aios_assistant/src/controller.dart';
import 'package:aios_assistant/src/core_manager.dart';
import 'package:aios_assistant/src/shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'native snapshot restores accounts and intelligence before core startup',
    () async {
      final directory = await Directory.systemTemp.createTemp(
        'aios-native-cache-',
      );
      final snapshot = File('${directory.path}\\snapshot.json');
      final preferences = File('${directory.path}\\preferences.json');
      addTearDown(() => directory.delete(recursive: true));
      final onlineApi = _SnapshotApi({
        '/api/live': {
          'stats': {'opportunities': 7, 'active_reminders': 3},
          'inbox_items': [
            {'subject': 'Saved email summary'},
          ],
        },
        '/api/desktop/status': {'startup': {}},
        '/api/intelligence/accounts': {
          'accounts': [
            {'id': 1, 'email': 'saved@example.com'},
          ],
        },
        '/api/workers': {'items': []},
      });
      final first = AiosController(
        api: onlineApi,
        core: _SnapshotCore(onlineApi),
        preferencesFile: preferences,
        snapshotFile: snapshot,
      );
      await first.initialize();
      first.dispose();

      final offlineApi = _SnapshotApi(const {});
      final restored = AiosController(
        api: offlineApi,
        core: _SnapshotCore(offlineApi, fail: true),
        preferencesFile: preferences,
        snapshotFile: snapshot,
      );
      await restored.initialize();
      addTearDown(restored.dispose);

      expect(restored.live['stats'], {
        'opportunities': 7,
        'active_reminders': 3,
      });
      expect(
        (restored.accounts['accounts'] as List).first['email'],
        'saved@example.com',
      );
      expect(restored.message, contains('Core unavailable'));
    },
  );

  testWidgets('native shell renders local intelligence dashboard', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(1280, 760);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final controller = AiosController()
      ..loading = false
      ..message = 'Private core connected'
      ..live = {
        'stats': {'opportunities': 3, 'active_reminders': 2},
        'intelligence': {
          'unread_emails': 8,
          'today': {
            'summary': 'Two tasks selected',
            'items': [
              {'title': 'Reply to project mail', 'time': '09:00'},
            ],
          },
        },
      };
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(home: AiosShell(controller: controller)),
    );
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('Overview'), findsWidgets);
    expect(find.text('WORKSPACE'), findsOneWidget);
    expect(find.text('Opportunity pipeline'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
    expect(find.text('Projects'), findsNothing);
    expect(find.text('Wellbeing'), findsNothing);
    expect(find.text('Planner'), findsNothing);
    expect(find.text('Command Planner'), findsNothing);
    expect(find.text('Automation'), findsNothing);
    expect(find.text('Browser Agent'), findsNothing);
    expect(find.text('Career Copilot'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('memory restores checkpoints and connected context', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(1280, 760);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final controller = AiosController()
      ..loading = false
      ..activePage = 'memory';
    controller.pageData['memory'] = {
      'counts': {'projects': 1, 'entities': 2, 'facts': 3, 'relations': 1},
      'projects': [
        {
          'name': 'FlightIQ',
          'status': 'active',
          'summary': 'Flight dashboard',
          'latest_checkpoint': {
            'summary': 'Stopped after wiring airport search.',
            'active_tasks': ['Finish filters'],
            'next_actions': ['Open dashboard.dart'],
            'open_files': ['dashboard.dart'],
          },
        },
      ],
      'entities': [
        {
          'name': 'FlightIQ',
          'entity_type': 'project',
          'summary': 'Flight dashboard',
        },
      ],
      'recent_facts': [
        {
          'content': 'Use the compact airport dataset.',
          'source': 'native AiOS memory',
          'fact_type': 'note',
        },
      ],
    };
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(home: AiosShell(controller: controller)),
    );
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('Continue where you stopped.'), findsOneWidget);
    expect(find.text('Ask Memory'), findsOneWidget);
    expect(find.text('Save checkpoint'), findsOneWidget);
    expect(find.text('FlightIQ'), findsWidgets);
    expect(find.textContaining('Open dashboard.dart'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('sidebar keeps its scroll position when a lower page opens', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(1280, 760);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final controller = AiosController()..loading = false;
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(home: AiosShell(controller: controller)),
    );
    await tester.pump(const Duration(milliseconds: 500));

    final sidebar = find.byKey(const PageStorageKey('aios-sidebar-navigation'));
    await tester.drag(sidebar, const Offset(0, -560));
    await tester.pump(const Duration(milliseconds: 500));
    final scrollable = tester.state<ScrollableState>(
      find.descendant(of: sidebar, matching: find.byType(Scrollable)),
    );
    final before = scrollable.position.pixels;

    await tester.tap(find.text('Settings'));
    await tester.pump(const Duration(milliseconds: 500));

    expect(controller.activePage, 'settings');
    expect(scrollable.position.pixels, closeTo(before, 0.1));
    expect(tester.takeException(), isNull);
  });

  testWidgets('compact desktop shell has no layout overflow', (tester) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(900, 700);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final controller = AiosController()..loading = false;
    addTearDown(controller.dispose);

    await tester.pumpWidget(
      MaterialApp(home: AiosShell(controller: controller)),
    );
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('Opportunity pipeline'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('retained pages expose native actions without overflow', (
    tester,
  ) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = const Size(900, 700);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.view.resetPhysicalSize);
    final controller = AiosController()
      ..loading = false
      ..live = {
        'reminders': [
          {
            'id': 1,
            'title': 'Reply to the internship email',
            'due_at': '2026-07-17T12:00:00',
            'priority': 'high',
            'is_read': false,
          },
        ],
        'opportunities': [
          {'title': 'PromptWars', 'kind': 'hackathon', 'status': 'building'},
        ],
        'inbox_items': [
          {
            'subject': 'Round two invitation',
            'category': 'internship',
            'summary': 'Prepare the requested documents.',
            'confidence': 0.9,
          },
        ],
      }
      ..accounts = {
        'accounts': [
          {
            'id': 1,
            'email': 'student@example.com',
            'label': 'College',
            'sync_enabled': true,
          },
        ],
        'google_client': {'configured': true},
      }
      ..workers = [
        {
          'id': 'email_intelligence',
          'name': 'Email Intelligence Planner',
          'description': 'Keeps local email plans current.',
          'running': true,
        },
      ]
      ..desktop = {
        'startup': {'enabled': true, 'background': true},
      };
    controller.pageData['connectors'] = {
      'items': [
        {
          'id': 'gmail',
          'name': 'Gmail',
          'description': 'Synchronizes connected accounts.',
          'setup': 'One account connected.',
          'configured': true,
        },
      ],
    };
    addTearDown(controller.dispose);

    Future<void> showPage(String page) async {
      controller.activePage = page;
      await tester.pumpWidget(
        MaterialApp(home: AiosShell(controller: controller)),
      );
      await tester.pump(const Duration(milliseconds: 500));
      expect(tester.takeException(), isNull, reason: '$page overflowed');
    }

    await showPage('opportunities');
    expect(find.text('Run scan'), findsOneWidget);

    await showPage('reminders');
    expect(find.text('Mark read'), findsOneWidget);
    expect(find.text('Complete task'), findsOneWidget);

    await showPage('inbox');
    expect(find.text('Sync inbox'), findsOneWidget);

    await showPage('sources');
    expect(find.byTooltip('Rename account'), findsOneWidget);
    expect(find.byTooltip('Pause sync'), findsOneWidget);

    await showPage('connectors');
    expect(find.text('Run'), findsOneWidget);

    await showPage('workers');
    expect(find.text('Stop'), findsOneWidget);

    await showPage('settings');
    expect(find.text('Start minimized in tray'), findsOneWidget);
  });

  test(
    'reminder actions update read state and remove completed work',
    () async {
      final api = _ReminderActionApi();
      final controller = AiosController(api: api)
        ..loading = false
        ..live = {
          'stats': {'active_reminders': 1},
          'reminders': [api.reminder],
        };
      controller.pageData['reminders'] = {
        'items': [api.reminder],
        'stats': {
          'open': 1,
          'overdue': 1,
          'due_today': 0,
          'unread': 1,
          'completed_today': 0,
        },
      };
      addTearDown(controller.dispose);

      await controller.updateReminder(7, done: false);
      expect(controller.live['reminders'][0]['is_read'], isTrue);
      expect(controller.pageData['reminders']!['stats']['unread'], 0);
      expect(api.paths, contains('/api/reminders/7/read'));

      await controller.updateReminder(7, done: true);
      expect(controller.live['reminders'], isEmpty);
      expect(controller.pageData['reminders']!['items'], isEmpty);
      expect(controller.pageData['reminders']!['stats']['completed_today'], 1);
      expect(api.paths, contains('/api/reminders/7/done'));
    },
  );
}

class _SnapshotApi extends AiosApi {
  _SnapshotApi(this.responses);

  final Map<String, Map<String, dynamic>> responses;

  @override
  Future<Map<String, dynamic>> get(String path) async {
    final response = responses[path];
    if (response == null) throw StateError('API unavailable');
    return response;
  }
}

class _SnapshotCore extends CoreManager {
  _SnapshotCore(AiosApi api, {this.fail = false}) : super(api: api);

  final bool fail;

  @override
  Future<void> ensureRunning() async {
    if (fail) throw StateError('Core unavailable');
  }

  @override
  Future<void> stop() async {}
}

class _ReminderActionApi extends AiosApi {
  bool read = false;
  bool done = false;
  final List<String> paths = [];

  Map<String, dynamic> get reminder => {
    'id': 7,
    'title': 'Confirm interview slot',
    'due_at': '2026-07-20T12:00:00',
    'due_label': 'Overdue by 1 day',
    'urgency': 'overdue',
    'priority': 'high',
    'source': 'Gmail',
    'email_subject': 'Interview confirmation needed',
    'email_account': 'student@example.com',
    'context': 'student@example.com • jobs@example.com',
    'why': 'This task is overdue and needs a decision now.',
    'is_read': read,
    'is_done': done,
  };

  @override
  Future<Map<String, dynamic>> post(
    String path, [
    Map<String, dynamic> body = const {},
  ]) async {
    paths.add(path);
    if (path.endsWith('/read')) read = true;
    if (path.endsWith('/done')) {
      read = true;
      done = true;
    }
    return {
      'ok': true,
      'message': done ? 'Reminder completed.' : 'Reminder marked as read.',
      'reminder': reminder,
    };
  }

  @override
  Future<Map<String, dynamic>> get(String path) async => switch (path) {
    '/api/reminders/overview' => {
      'items': done ? <dynamic>[] : [reminder],
      'stats': {
        'open': done ? 0 : 1,
        'overdue': done ? 0 : 1,
        'due_today': 0,
        'unread': done || read ? 0 : 1,
        'completed_today': done ? 1 : 0,
      },
    },
    '/api/live' => {
      'stats': {'active_reminders': done ? 0 : 1},
      'reminders': done ? <dynamic>[] : [reminder],
    },
    '/api/desktop/status' => const {},
    '/api/intelligence/accounts' => const {},
    '/api/workers' => {'items': <dynamic>[]},
    _ => throw StateError('Unexpected path $path'),
  };
}
