import 'package:flutter/material.dart';

import 'controller.dart';

class AiosShell extends StatelessWidget {
  const AiosShell({required this.controller, super.key});

  final AiosController controller;

  static const destinations = [
    ('overview', 'Overview', Icons.dashboard_outlined),
    ('inbox', 'Inbox AI', Icons.mark_email_unread_outlined),
    ('opportunities', 'Opportunities', Icons.work_outline),
    ('projects', 'Projects', Icons.account_tree_outlined),
    ('college', 'College', Icons.school_outlined),
    ('accounts', 'Accounts', Icons.alternate_email),
    ('settings', 'Settings', Icons.tune_outlined),
  ];

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.sizeOf(context).width < 900;
    return Scaffold(
      body: SafeArea(
        child: Row(
          children: [
            if (!narrow) _Sidebar(controller: controller),
            Expanded(
              child: Column(
                children: [
                  _TopBar(controller: controller),
                  Expanded(
                    child: AnimatedSwitcher(
                      duration: const Duration(milliseconds: 220),
                      child: _ActivePage(
                        key: ValueKey(controller.activePage),
                        controller: controller,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: narrow
          ? NavigationBar(
              selectedIndex: destinations
                  .map((item) => item.$1)
                  .toList()
                  .indexOf(controller.activePage)
                  .clamp(0, destinations.length - 1),
              onDestinationSelected: (index) =>
                  controller.selectPage(destinations[index].$1),
              destinations: destinations
                  .map(
                    (item) => NavigationDestination(
                      icon: Icon(item.$3),
                      label: item.$2,
                    ),
                  )
                  .toList(),
            )
          : null,
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      width: 224,
      decoration: BoxDecoration(
        color: colors.surfaceContainerLow,
        border: Border(right: BorderSide(color: colors.outlineVariant)),
      ),
      child: Column(
        children: [
          const SizedBox(height: 22),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: colors.primary,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    'A',
                    style: TextStyle(
                      color: colors.onPrimary,
                      fontWeight: FontWeight.w900,
                      fontSize: 20,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'AiOS',
                        style: TextStyle(fontWeight: FontWeight.w800),
                      ),
                      Text('Private life OS', style: TextStyle(fontSize: 12)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              children: AiosShell.destinations
                  .map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: ListTile(
                        dense: true,
                        selected: controller.activePage == item.$1,
                        selectedTileColor: colors.primary,
                        selectedColor: colors.onPrimary,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(7),
                        ),
                        leading: Icon(item.$3, size: 20),
                        title: Text(
                          item.$2,
                          style: const TextStyle(fontWeight: FontWeight.w700),
                        ),
                        onTap: () => controller.selectPage(item.$1),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: colors.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(
                    Icons.circle,
                    size: 10,
                    color: controller.api.connected
                        ? const Color(0xFFA7FF3C)
                        : colors.error,
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text(
                      controller.api.connected
                          ? 'Core connected'
                          : 'Core offline',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
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

class _TopBar extends StatelessWidget {
  const _TopBar({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Container(
      height: 70,
      padding: const EdgeInsets.symmetric(horizontal: 22),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: colors.outlineVariant)),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _pageTitle(controller.activePage),
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  controller.message,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    color: colors.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Refresh',
            onPressed: controller.loading ? null : controller.refresh,
            icon: controller.loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Theme',
            onPressed: controller.toggleTheme,
            icon: Icon(
              controller.darkMode ? Icons.light_mode : Icons.dark_mode,
            ),
          ),
          const SizedBox(width: 6),
          FilledButton.icon(
            onPressed: controller.syncing ? null : controller.syncAll,
            icon: controller.syncing
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync, size: 18),
            label: const Text('Sync'),
          ),
        ],
      ),
    );
  }

  static String _pageTitle(String value) => AiosShell.destinations
      .firstWhere(
        (item) => item.$1 == value,
        orElse: () => AiosShell.destinations.first,
      )
      .$2;
}

class _ActivePage extends StatelessWidget {
  const _ActivePage({required this.controller, super.key});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final child = switch (controller.activePage) {
      'inbox' => _InboxPage(controller: controller),
      'opportunities' => _OpportunitiesPage(controller: controller),
      'projects' => _ProjectsPage(controller: controller),
      'college' => _CollegePage(controller: controller),
      'accounts' => _AccountsPage(controller: controller),
      'settings' => _SettingsPage(controller: controller),
      _ => _OverviewPage(controller: controller),
    };
    return SingleChildScrollView(
      key: ValueKey(controller.activePage),
      padding: const EdgeInsets.all(22),
      child: child,
    );
  }
}

class _OverviewPage extends StatelessWidget {
  const _OverviewPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final stats = _map(controller.live['stats']);
    final intelligence = _map(controller.live['intelligence']);
    final today = _map(intelligence['today']);
    final reminders = _maps(controller.live['reminders']);
    final planItems = _maps(today['items']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Heading('Today', 'Your current local briefing'),
        const SizedBox(height: 16),
        LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth > 1000
                ? (constraints.maxWidth - 36) / 4
                : (constraints.maxWidth - 12) / 2;
            return Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                _Metric(
                  width,
                  'Opportunities',
                  '${stats['opportunities'] ?? 0}',
                  Icons.work_outline,
                ),
                _Metric(
                  width,
                  'Reminders',
                  '${stats['active_reminders'] ?? 0}',
                  Icons.notifications_none,
                ),
                _Metric(
                  width,
                  'Unread mail',
                  '${intelligence['unread_emails'] ?? 0}',
                  Icons.mark_email_unread_outlined,
                ),
                _Metric(
                  width,
                  'Focus minutes',
                  '${stats['wellbeing_minutes'] ?? 0}',
                  Icons.timer_outlined,
                ),
              ],
            );
          },
        ),
        const SizedBox(height: 22),
        _Section(
          title: 'Today\'s focus',
          trailing: today['summary']?.toString() ?? '',
          children: planItems.isEmpty
              ? const [_Empty('No planned work yet.')]
              : planItems
                    .take(8)
                    .map(
                      (item) => _RowItem(
                        icon: Icons.check_circle_outline,
                        title: item['title']?.toString() ?? 'Planned task',
                        subtitle:
                            item['time']?.toString() ??
                            item['source']?.toString() ??
                            '',
                      ),
                    )
                    .toList(),
        ),
        const SizedBox(height: 14),
        _Section(
          title: 'Due reminders',
          children: reminders.isEmpty
              ? const [_Empty('Nothing urgent right now.')]
              : reminders
                    .take(6)
                    .map(
                      (item) => _RowItem(
                        icon: Icons.alarm,
                        title: item['title']?.toString() ?? 'Reminder',
                        subtitle: item['due_at']?.toString() ?? '',
                      ),
                    )
                    .toList(),
        ),
      ],
    );
  }
}

class _InboxPage extends StatelessWidget {
  const _InboxPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final items = _maps(controller.live['inbox_items']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Heading('Inbox AI', 'Latest locally summarized email signals'),
        const SizedBox(height: 16),
        if (items.isEmpty)
          const _Empty('No analyzed email is available.')
        else
          ...items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _Section(
                title: item['subject']?.toString() ?? 'Email',
                trailing: item['category']?.toString() ?? '',
                children: [
                  Text(
                    item['summary']?.toString() ?? '',
                    maxLines: 4,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if ((item['next_action']?.toString() ?? '').isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: Text('Next: ${item['next_action']}'),
                    ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class _OpportunitiesPage extends StatelessWidget {
  const _OpportunitiesPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final achievements = _maps(controller.live['achievements']);
    final deadlines = _maps(controller.live['deadline_highlights']);
    final opportunities = _maps(controller.live['opportunities']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Heading(
          'Opportunities',
          'Achievements, deadlines and active applications',
        ),
        const SizedBox(height: 16),
        _Section(
          title: 'Achievements',
          children: achievements.isEmpty
              ? const [_Empty('No selection updates yet.')]
              : achievements
                    .map(
                      (item) => _RowItem(
                        icon: Icons.verified_outlined,
                        title: item['status']?.toString() ?? 'Achievement',
                        subtitle: item['title']?.toString() ?? '',
                      ),
                    )
                    .toList(),
        ),
        const SizedBox(height: 14),
        _Section(
          title: 'Build timeline',
          children: deadlines.isEmpty
              ? const [_Empty('No active submission deadline.')]
              : deadlines
                    .map(
                      (item) => _RowItem(
                        icon: Icons.event_available_outlined,
                        title:
                            item['program']?.toString() ??
                            item['title']?.toString() ??
                            'Deadline',
                        subtitle: item['deadline_message']?.toString() ?? '',
                      ),
                    )
                    .toList(),
        ),
        const SizedBox(height: 14),
        _Section(
          title: 'Pipeline',
          children: opportunities.isEmpty
              ? const [_Empty('No tracked opportunity.')]
              : opportunities
                    .map(
                      (item) => _RowItem(
                        icon: Icons.arrow_outward,
                        title: item['title']?.toString() ?? 'Opportunity',
                        subtitle:
                            '${item['status'] ?? ''} · ${item['organization'] ?? ''}',
                      ),
                    )
                    .toList(),
        ),
      ],
    );
  }
}

class _ProjectsPage extends StatelessWidget {
  const _ProjectsPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final projects = _maps(controller.projects['projects']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Heading(
          'Projects',
          'Grouped repository and local workspace context',
        ),
        const SizedBox(height: 16),
        if (projects.isEmpty)
          const _Empty('No project context yet.')
        else
          ...projects.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _ProjectCard(item: item),
            ),
          ),
      ],
    );
  }
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final progress = (item['progress'] as num?)?.toDouble() ?? 0;
    return _Section(
      title: item['title']?.toString() ?? 'Project',
      trailing: '${progress.round()}%',
      children: [
        LinearProgressIndicator(value: (progress / 100).clamp(0, 1)),
        const SizedBox(height: 12),
        Text(item['next_action']?.toString() ?? 'Choose the next action.'),
        if ((item['repository']?.toString() ?? '').isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(item['repository'].toString()),
          ),
        if ((item['grouped_updates'] as num?) != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('${item['grouped_updates']} updates grouped'),
          ),
      ],
    );
  }
}

class _CollegePage extends StatelessWidget {
  const _CollegePage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final updates = _maps(controller.college['updates']);
    final bring = _strings(controller.college['bring']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Heading('College', 'PAT schedule and preparation'),
        const SizedBox(height: 16),
        _Section(
          title: controller.college['headline']?.toString() ?? 'PAT status',
          trailing:
              '${controller.college['emails_scanned'] ?? 0} mails scanned',
          children: [
            Text(controller.college['latest_summary']?.toString() ?? ''),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _Chip(
                  Icons.schedule,
                  controller.college['time']?.toString() ?? 'Time not stated',
                ),
                _Chip(
                  Icons.location_on_outlined,
                  controller.college['location']?.toString() ??
                      'Location not stated',
                ),
                ...bring.map((item) => _Chip(Icons.check, item)),
              ],
            ),
          ],
        ),
        const SizedBox(height: 14),
        _Section(
          title: 'Mail timeline',
          children: updates.isEmpty
              ? const [_Empty('No PAT update found.')]
              : updates
                    .take(8)
                    .map(
                      (item) => _RowItem(
                        icon: Icons.mail_outline,
                        title: item['subject']?.toString() ?? 'PAT notice',
                        subtitle: item['summary']?.toString() ?? '',
                      ),
                    )
                    .toList(),
        ),
      ],
    );
  }
}

class _AccountsPage extends StatelessWidget {
  const _AccountsPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final accounts = _maps(controller.accounts['accounts']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Heading('Google accounts', 'Read-only Gmail connections'),
        const SizedBox(height: 16),
        if (controller.signIn != null)
          _SignInPanel(controller: controller)
        else
          SizedBox(
            width: 260,
            child: FilledButton.icon(
              onPressed: controller.connectGoogle,
              icon: const Icon(Icons.login),
              label: Text(
                accounts.isEmpty ? 'Sign in with Google' : 'Add Google account',
              ),
            ),
          ),
        const SizedBox(height: 18),
        if (accounts.isEmpty)
          const _Empty('No Gmail account connected.')
        else
          ...accounts.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _AccountRow(controller: controller, item: item),
            ),
          ),
      ],
    );
  }
}

class _SignInPanel extends StatelessWidget {
  const _SignInPanel({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final signIn = controller.signIn!;
    return _Section(
      title: 'Continue in browser',
      trailing: signIn['status']?.toString() ?? 'starting',
      children: [
        const LinearProgressIndicator(),
        const SizedBox(height: 12),
        Text(signIn['message']?.toString() ?? 'Preparing secure sign-in...'),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: controller.cancelGoogleSignIn,
          icon: const Icon(Icons.close),
          label: const Text('Cancel sign-in'),
        ),
      ],
    );
  }
}

class _AccountRow extends StatelessWidget {
  const _AccountRow({required this.controller, required this.item});
  final AiosController controller;
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final id = (item['id'] as num?)?.toInt() ?? 0;
    return _Section(
      title:
          item['label']?.toString() ??
          item['email']?.toString() ??
          'Google account',
      trailing: item['sync_enabled'] == false ? 'Paused' : 'Syncing',
      children: [
        Text(item['email']?.toString() ?? ''),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          children: [
            FilledButton.tonalIcon(
              onPressed: controller.syncing
                  ? null
                  : () => controller.syncAccount(id),
              icon: const Icon(Icons.sync, size: 18),
              label: const Text('Sync now'),
            ),
            OutlinedButton.icon(
              onPressed: () => controller.removeAccount(id),
              icon: const Icon(Icons.link_off, size: 18),
              label: const Text('Disconnect'),
            ),
          ],
        ),
      ],
    );
  }
}

class _SettingsPage extends StatelessWidget {
  const _SettingsPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final running = controller.workers
        .where((item) => _map(item)['running'] == true)
        .length;
    final startup = _map(controller.desktop['startup']);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _Heading('Settings', 'Native runtime and local services'),
        const SizedBox(height: 16),
        _Section(
          title: 'Runtime',
          children: [
            _KeyValue('Client', 'Flutter native Windows'),
            _KeyValue(
              'Core API',
              controller.api.baseUrl.isEmpty
                  ? 'Starting'
                  : controller.api.baseUrl,
            ),
            _KeyValue('Data', controller.desktop['data_dir']?.toString() ?? ''),
            _KeyValue(
              'Workers',
              '$running of ${controller.workers.length} running',
            ),
          ],
        ),
        const SizedBox(height: 14),
        _Section(
          title: 'Application',
          children: [
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: controller.darkMode,
              onChanged: (_) => controller.toggleTheme(),
              title: const Text('Dark mode'),
              secondary: const Icon(Icons.dark_mode_outlined),
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              value: startup['enabled'] == true,
              onChanged: (value) => controller.setStartup(enabled: value),
              title: const Text('Open on Windows startup'),
              subtitle: const Text('Starts quietly in the system tray'),
              secondary: const Icon(Icons.rocket_launch_outlined),
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.keyboard_arrow_down),
              title: const Text('Hide to tray'),
              onTap: controller.hideToTray,
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.power_settings_new),
              title: const Text('Exit AiOS'),
              onTap: controller.exitApp,
            ),
          ],
        ),
      ],
    );
  }
}

class _Heading extends StatelessWidget {
  const _Heading(this.title, this.subtitle);
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        title,
        style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 4),
      Text(
        subtitle,
        style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
      ),
    ],
  );
}

class _Metric extends StatelessWidget {
  const _Metric(this.width, this.label, this.value, this.icon);
  final double width;
  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) => SizedBox(
    width: width,
    height: 132,
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon),
            const Spacer(),
            Text(
              value,
              style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800),
            ),
            Text(label),
          ],
        ),
      ),
    ),
  );
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.children,
    this.trailing = '',
  });
  final String title;
  final String trailing;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              if (trailing.isNotEmpty)
                Text(
                  trailing,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 14),
          ...children,
        ],
      ),
    ),
  );
}

class _RowItem extends StatelessWidget {
  const _RowItem({
    required this.icon,
    required this.title,
    required this.subtitle,
  });
  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
              if (subtitle.isNotEmpty)
                Text(subtitle, maxLines: 3, overflow: TextOverflow.ellipsis),
            ],
          ),
        ),
      ],
    ),
  );
}

class _Empty extends StatelessWidget {
  const _Empty(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 16),
    child: Center(child: Text(text)),
  );
}

class _Chip extends StatelessWidget {
  const _Chip(this.icon, this.label);
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) => Chip(
    avatar: Icon(icon, size: 16),
    label: Text(label.isEmpty ? 'Not stated' : label),
  );
}

class _KeyValue extends StatelessWidget {
  const _KeyValue(this.label, this.value);
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      children: [
        SizedBox(width: 120, child: Text(label)),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
      ],
    ),
  );
}

Map<String, dynamic> _map(dynamic value) =>
    value is Map<String, dynamic> ? value : const {};
List<Map<String, dynamic>> _maps(dynamic value) =>
    (value as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .toList();
List<String> _strings(dynamic value) => (value as List<dynamic>? ?? const [])
    .map((item) => item.toString())
    .toList();
