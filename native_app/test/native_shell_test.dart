import 'package:aios_assistant/src/controller.dart';
import 'package:aios_assistant/src/shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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
}
