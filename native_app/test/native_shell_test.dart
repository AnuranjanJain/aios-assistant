import 'package:aios_assistant/src/controller.dart';
import 'package:aios_assistant/src/shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('native shell renders local intelligence dashboard', (
    tester,
  ) async {
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

    expect(find.text('Overview'), findsWidgets);
    expect(find.text('Reply to project mail'), findsOneWidget);
    expect(find.text('3'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
