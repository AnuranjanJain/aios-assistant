import 'dart:async';

import 'package:flutter/material.dart';

import 'controller.dart';

class AiosShell extends StatefulWidget {
  const AiosShell({required this.controller, super.key});

  final AiosController controller;

  static const destinations = <({String id, String label, IconData icon})>[
    (id: 'overview', label: 'Overview', icon: Icons.grid_view_rounded),
    (id: 'opportunities', label: 'Opportunities', icon: Icons.work_outline),
    (id: 'reminders', label: 'Reminders', icon: Icons.notifications_none),
    (id: 'inbox', label: 'Inbox AI', icon: Icons.mail_outline),
    (id: 'memory', label: 'Memory', icon: Icons.storage_outlined),
    (id: 'sources', label: 'Sources', icon: Icons.power_outlined),
    (id: 'connectors', label: 'Connectors', icon: Icons.link_rounded),
    (id: 'workers', label: 'Workers', icon: Icons.memory_outlined),
    (id: 'settings', label: 'Settings', icon: Icons.tune_outlined),
  ];

  @override
  State<AiosShell> createState() => _AiosShellState();
}

class _AiosShellState extends State<AiosShell> {
  final ScrollController _sidebarScroll = ScrollController();

  @override
  void dispose() {
    _sidebarScroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final compactSidebar = width < 1040;
    final showSchedule = width >= 1120;
    final outerPadding = width < 900 ? 12.0 : 20.0;
    final shellGap = width < 900 ? 12.0 : 20.0;
    return Scaffold(
      backgroundColor: _Palette.of(context).background,
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.all(outerPadding),
          child: Row(
            children: [
              _Sidebar(
                controller: widget.controller,
                scrollController: _sidebarScroll,
                compact: compactSidebar,
              ),
              SizedBox(width: shellGap),
              Expanded(
                child: Column(
                  children: [
                    _TopBar(
                      controller: widget.controller,
                      showSchedule: showSchedule,
                    ),
                    const SizedBox(height: 18),
                    if (_isDashboardPage(widget.controller.activePage)) ...[
                      _DashboardTabs(controller: widget.controller),
                      const SizedBox(height: 18),
                    ],
                    Expanded(
                      child: ClipRect(
                        child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 420),
                          switchInCurve: const Cubic(0.2, 0.8, 0.2, 1),
                          layoutBuilder: (currentChild, previousChildren) =>
                              currentChild ?? const SizedBox.shrink(),
                          transitionBuilder: (child, animation) {
                            final curved = CurvedAnimation(
                              parent: animation,
                              curve: const Cubic(0.2, 0.8, 0.2, 1),
                            );
                            return FadeTransition(
                              opacity: curved,
                              child: SlideTransition(
                                position: Tween(
                                  begin: const Offset(0, 0.025),
                                  end: Offset.zero,
                                ).animate(curved),
                                child: ScaleTransition(
                                  scale: Tween(
                                    begin: 0.992,
                                    end: 1.0,
                                  ).animate(curved),
                                  child: child,
                                ),
                              ),
                            );
                          },
                          child: _ActivePage(
                            key: ValueKey(widget.controller.activePage),
                            controller: widget.controller,
                          ),
                        ),
                      ),
                    ),
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

bool _isDashboardPage(String page) =>
    const {'overview', 'opportunities', 'reminders', 'inbox'}.contains(page);

class _Sidebar extends StatelessWidget {
  const _Sidebar({
    required this.controller,
    required this.scrollController,
    required this.compact,
  });

  final AiosController controller;
  final ScrollController scrollController;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    return AnimatedContainer(
      duration: const Duration(milliseconds: 240),
      width: compact ? 88 : 232,
      decoration: BoxDecoration(
        color: palette.sidebar,
        border: Border.all(color: palette.border),
        borderRadius: BorderRadius.circular(16),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _Brand(compact: compact),
          const SizedBox(height: 18),
          Expanded(
            child: Scrollbar(
              controller: scrollController,
              thumbVisibility: true,
              thickness: 5,
              radius: const Radius.circular(20),
              child: ListView.separated(
                key: const PageStorageKey('aios-sidebar-navigation'),
                controller: scrollController,
                padding: const EdgeInsets.only(right: 8),
                itemCount: AiosShell.destinations.length,
                separatorBuilder: (_, _) => const SizedBox(height: 5),
                itemBuilder: (context, index) {
                  final item = AiosShell.destinations[index];
                  return _SidebarItem(
                    item: item,
                    compact: compact,
                    selected: controller.activePage == item.id,
                    onTap: () => controller.selectPage(item.id),
                  );
                },
              ),
            ),
          ),
          const SizedBox(height: 12),
          _AgentStatus(controller: controller, compact: compact),
          const SizedBox(height: 9),
          _ShellButton(
            tooltip: 'Lock workspace',
            onTap: controller.hideToTray,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.lock_outline, size: 17),
                if (!compact) ...[
                  const SizedBox(width: 8),
                  const Flexible(
                    child: Text(
                      'Lock workspace',
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontWeight: FontWeight.w800),
                    ),
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

class _Brand extends StatelessWidget {
  const _Brand({required this.compact});
  final bool compact;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Container(
        width: 46,
        height: 46,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(13),
          boxShadow: const [
            BoxShadow(color: Color(0x1FA7FF3C), spreadRadius: 7, blurRadius: 2),
          ],
        ),
        clipBehavior: Clip.antiAlias,
        child: Image.asset(
          'assets/aios-logo-512.png',
          fit: BoxFit.cover,
          filterQuality: FilterQuality.high,
        ),
      ),
      if (!compact) ...[
        const SizedBox(width: 12),
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'WORKSPACE',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900),
              ),
              SizedBox(height: 2),
              Text(
                'AiOS local agent',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 12, color: _Palette.mutedDark),
              ),
            ],
          ),
        ),
      ],
    ],
  );
}

class _SidebarItem extends StatelessWidget {
  const _SidebarItem({
    required this.item,
    required this.compact,
    required this.selected,
    required this.onTap,
  });

  final ({String id, String label, IconData icon}) item;
  final bool compact;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    return Tooltip(
      message: compact ? item.label : '',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 240),
            curve: const Cubic(0.2, 0.8, 0.2, 1),
            height: 38,
            decoration: BoxDecoration(
              color: selected ? _Palette.primary : Colors.transparent,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: selected ? _Palette.primary : Colors.transparent,
              ),
            ),
            padding: EdgeInsets.symmetric(horizontal: compact ? 8 : 10),
            child: Row(
              mainAxisAlignment: compact
                  ? MainAxisAlignment.center
                  : MainAxisAlignment.start,
              children: [
                AnimatedScale(
                  duration: const Duration(milliseconds: 240),
                  scale: selected ? 1 : 0.96,
                  child: Container(
                    width: 26,
                    height: 26,
                    decoration: BoxDecoration(
                      color: selected
                          ? const Color(0x14000000)
                          : palette.surfaceRaised,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    alignment: Alignment.center,
                    child: Icon(
                      item.icon,
                      size: 19,
                      color: selected ? const Color(0xFF10150C) : palette.text,
                    ),
                  ),
                ),
                if (!compact) ...[
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      item.label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: selected
                            ? const Color(0xFF10150C)
                            : palette.muted,
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AgentStatus extends StatelessWidget {
  const _AgentStatus({required this.controller, required this.compact});
  final AiosController controller;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    final connected = controller.api.connected;
    return Container(
      width: double.infinity,
      constraints: const BoxConstraints(minHeight: 56),
      decoration: BoxDecoration(
        color: palette.surfaceRaised,
        border: Border.all(color: palette.border),
        borderRadius: BorderRadius.circular(16),
      ),
      padding: EdgeInsets.all(compact ? 10 : 12),
      child: Row(
        mainAxisAlignment: compact
            ? MainAxisAlignment.center
            : MainAxisAlignment.start,
        children: [
          _LiveDot(connected: connected),
          if (!compact) ...[
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    connected ? 'Live local agent' : 'Local agent offline',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    connected ? 'Live sync now' : 'Starting private core',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 12, color: palette.muted),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _LiveDot extends StatefulWidget {
  const _LiveDot({required this.connected});
  final bool connected;

  @override
  State<_LiveDot> createState() => _LiveDotState();
}

class _LiveDotState extends State<_LiveDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animation;

  @override
  void initState() {
    super.initState();
    _animation = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat();
  }

  @override
  void dispose() {
    _animation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: _animation,
    builder: (context, _) {
      final color = widget.connected ? _Palette.primary : _Palette.danger;
      return Container(
        width: 13,
        height: 13,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.32 * (1 - _animation.value)),
              spreadRadius: 2 + (_animation.value * 8),
              blurRadius: 1,
            ),
          ],
        ),
      );
    },
  );
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.controller, required this.showSchedule});
  final AiosController controller;
  final bool showSchedule;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    return SizedBox(
      height: 52,
      child: Row(
        children: [
          if (showSchedule) ...[
            Container(
              height: 52,
              constraints: const BoxConstraints(minWidth: 220, maxWidth: 260),
              decoration: BoxDecoration(
                color: palette.surface,
                border: Border.all(color: palette.border),
                borderRadius: BorderRadius.circular(16),
              ),
              padding: const EdgeInsets.all(4),
              child: Row(
                children: [
                  Container(
                    height: 38,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: palette.surfaceRaised,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    child: const Text(
                      'Local AI',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      controller.api.connected ? 'Live local sync' : 'Starting',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: _Palette.primary,
                        fontSize: 12,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 14),
          ],
          Expanded(child: _TopRail(controller: controller)),
          const SizedBox(width: 14),
          Tooltip(
            message: 'Settings and profile',
            child: InkWell(
              borderRadius: BorderRadius.circular(24),
              onTap: () => controller.selectPage('settings'),
              child: Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: palette.surface,
                  shape: BoxShape.circle,
                  border: Border.all(color: palette.border),
                ),
                alignment: Alignment.center,
                child: const Text(
                  'A',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TopRail extends StatelessWidget {
  const _TopRail({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final entries = <({String id, String label, IconData icon})>[
      (id: 'sources', label: 'Gmail', icon: Icons.mail_outline),
      (id: 'opportunities', label: 'Pipeline', icon: Icons.work_outline),
      (id: 'reminders', label: 'Reminders', icon: Icons.notifications_none),
      (id: 'memory', label: 'Memory', icon: Icons.storage_outlined),
      (id: 'inbox', label: 'Inbox AI', icon: Icons.auto_awesome_outlined),
    ];
    return Container(
      height: 52,
      decoration: BoxDecoration(
        color: _Palette.primary,
        borderRadius: BorderRadius.circular(16),
      ),
      padding: const EdgeInsets.all(4),
      child: Row(
        children: entries.map((entry) {
          final active = controller.activePage == entry.id;
          return Expanded(
            child: _RailItem(
              label: entry.label,
              icon: entry.icon,
              active: active,
              onTap: () => controller.selectPage(entry.id),
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _RailItem extends StatelessWidget {
  const _RailItem({
    required this.label,
    required this.icon,
    required this.active,
    required this.onTap,
  });
  final String label;
  final IconData icon;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: Colors.transparent,
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 140),
        decoration: BoxDecoration(
          color: active ? const Color(0x12000000) : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 17, color: const Color(0xFF10150C)),
            const SizedBox(width: 7),
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Color(0xFF10150C),
                  fontSize: 12,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _DashboardTabs extends StatelessWidget {
  const _DashboardTabs({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    const tabs = [
      ('overview', 'Overview'),
      ('opportunities', 'Opportunities'),
      ('reminders', 'Reminders'),
      ('inbox', 'Inbox AI'),
    ];
    return Container(
      height: 54,
      decoration: BoxDecoration(
        color: palette.surface,
        border: Border.all(color: palette.border),
        borderRadius: BorderRadius.circular(16),
      ),
      padding: const EdgeInsets.all(5),
      child: Row(
        children: tabs.map((tab) {
          final selected = controller.activePage == tab.$1;
          return Expanded(
            child: Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: () => controller.selectPage(tab.$1),
                borderRadius: BorderRadius.circular(12),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 240),
                  curve: const Cubic(0.2, 0.8, 0.2, 1),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: selected ? _Palette.primary : Colors.transparent,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: AnimatedDefaultTextStyle(
                    duration: const Duration(milliseconds: 140),
                    style: TextStyle(
                      color: selected ? const Color(0xFF10150C) : palette.muted,
                      fontSize: 14,
                      fontWeight: FontWeight.w900,
                    ),
                    child: Text(tab.$2),
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _ActivePage extends StatelessWidget {
  const _ActivePage({required this.controller, super.key});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final page = switch (controller.activePage) {
      'opportunities' => _OpportunitiesPage(controller: controller),
      'reminders' => _RemindersPage(controller: controller),
      'inbox' => _InboxPage(controller: controller),
      'memory' => _MemoryPage(controller: controller),
      'sources' => _SourcesPage(controller: controller),
      'connectors' => _ConnectorsPage(controller: controller),
      'workers' => _WorkersPage(controller: controller),
      'settings' => _SettingsPage(controller: controller),
      _ => _OverviewPage(controller: controller),
    };
    return Stack(
      children: [
        SingleChildScrollView(
          key: PageStorageKey('aios-page-${controller.activePage}'),
          padding: const EdgeInsets.only(bottom: 28),
          child: page,
        ),
        if (controller.pageLoading)
          const Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: LinearProgressIndicator(
              minHeight: 2,
              color: _Palette.primary,
              backgroundColor: Colors.transparent,
            ),
          ),
      ],
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
    final opportunities = [
      ..._maps(controller.live['achievements']),
      ..._maps(controller.live['opportunities']),
    ];
    final reminders = _maps(controller.live['reminders']);
    final summary = _string(
      today['summary'],
      fallback: 'Gmail, reminders, and memory are ready on this device.',
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Reveal(
          index: 0,
          child: _Hero(controller: controller, summary: summary),
        ),
        const SizedBox(height: 12),
        _MetricGrid(
          stats: stats,
          intelligence: intelligence,
          connectedAccounts: _maps(controller.accounts['accounts']).length,
        ),
        const SizedBox(height: 16),
        LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 820;
            final pipeline = _LeadSection(
              opportunities: opportunities,
              reminders: reminders,
              controller: controller,
            );
            final agent = _AgentSummary(
              summary: summary,
              latestInbox:
                  _maps(controller.live['inbox']).firstOrNull ?? const {},
            );
            if (!wide) {
              return Column(
                children: [pipeline, const SizedBox(height: 16), agent],
              );
            }
            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: pipeline),
                const SizedBox(width: 16),
                SizedBox(width: 320, child: agent),
              ],
            );
          },
        ),
        const SizedBox(height: 16),
        _OverviewDetails(controller: controller),
      ],
    );
  }
}

class _Hero extends StatelessWidget {
  const _Hero({required this.controller, required this.summary});
  final AiosController controller;
  final String summary;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width > 1120;
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 10, 2, 0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const _Eyebrow('PERSONAL AI PRODUCTIVITY SYSTEM'),
                Text(
                  '${_greeting()},\nAnuranjan.',
                  style: TextStyle(
                    fontSize: wide ? 62 : 48,
                    height: 0.98,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 13),
                Text(
                  summary,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: _Palette.of(context).muted,
                    fontSize: 14,
                    height: 1.45,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 20),
          SizedBox(
            width: 160,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _ActionButton(
                  label: 'Connect Sources',
                  primary: true,
                  onTap: () => controller.selectPage('sources'),
                ),
                const SizedBox(height: 9),
                _ActionButton(
                  label: 'Run Connectors',
                  onTap: () => controller.selectPage('connectors'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({
    required this.stats,
    required this.intelligence,
    required this.connectedAccounts,
  });
  final Map<String, dynamic> stats;
  final Map<String, dynamic> intelligence;
  final int connectedAccounts;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final columns = constraints.maxWidth >= 760 ? 4 : 2;
      final width = (constraints.maxWidth - ((columns - 1) * 16)) / columns;
      final values = [
        (
          'Tracked',
          '${stats['opportunities'] ?? 0}',
          'jobs, hackathons, interviews',
        ),
        ('Reminders', '${stats['active_reminders'] ?? 0}', 'open action items'),
        (
          'Unread Mail',
          '${intelligence['unread_emails'] ?? 0}',
          'across connected inboxes',
        ),
        ('Accounts', '$connectedAccounts', 'private Gmail sources'),
      ];
      return Wrap(
        spacing: 16,
        runSpacing: 16,
        children: values.indexed.map((entry) {
          final index = entry.$1;
          final item = entry.$2;
          return _Reveal(
            index: index + 1,
            child: SizedBox(
              width: width,
              child: _HoverSurface(
                height: 112,
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.$1,
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                    const Spacer(),
                    Text(
                      item.$2,
                      style: TextStyle(
                        color: index < 2 ? _Palette.primary : null,
                        fontSize: 32,
                        height: 1,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      item.$3,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: _Palette.of(context).muted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }).toList(),
      );
    },
  );
}

class _LeadSection extends StatelessWidget {
  const _LeadSection({
    required this.opportunities,
    required this.reminders,
    required this.controller,
  });
  final List<Map<String, dynamic>> opportunities;
  final List<Map<String, dynamic>> reminders;
  final AiosController controller;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      _Panel(
        eyebrow: 'NEW LEADS',
        title: 'Opportunity pipeline',
        action: _MiniButton(
          label: 'Run scan',
          onTap: controller.syncing ? null : controller.syncAll,
        ),
        child: opportunities.isEmpty
            ? const _Empty('No opportunities yet.')
            : LayoutBuilder(
                builder: (context, constraints) {
                  final columns = constraints.maxWidth > 580 ? 3 : 1;
                  final width =
                      (constraints.maxWidth - ((columns - 1) * 12)) / columns;
                  return Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: opportunities.take(6).toList().indexed.map((
                      entry,
                    ) {
                      final item = entry.$2;
                      return SizedBox(
                        width: width,
                        child: _Reveal(
                          index: entry.$1 + 5,
                          child: _LeadCard(item: item),
                        ),
                      );
                    }).toList(),
                  );
                },
              ),
      ),
      const SizedBox(height: 16),
      _Panel(
        eyebrow: 'YOUR DAY\'S TASKS',
        title: 'Next actions',
        child: reminders.isEmpty
            ? const _Empty('No urgent action is due right now.')
            : LayoutBuilder(
                builder: (context, constraints) {
                  final width = (constraints.maxWidth - 24) / 3;
                  return Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: reminders.take(3).toList().indexed.map((entry) {
                      final item = entry.$2;
                      return SizedBox(
                        width: width.clamp(170, constraints.maxWidth),
                        child: _TaskCard(item: item, accent: entry.$1 == 0),
                      );
                    }).toList(),
                  );
                },
              ),
      ),
    ],
  );
}

class _LeadCard extends StatelessWidget {
  const _LeadCard({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) => _HoverSurface(
    color: _Palette.of(context).surfaceRaised,
    padding: const EdgeInsets.all(13),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _StatusDot(),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _string(item['title'], fallback: 'Opportunity'),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '${_string(item['kind'])} - ${_string(item['status'])}',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: _Palette.of(context).muted,
                  fontSize: 12,
                  height: 1.45,
                ),
              ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _TaskCard extends StatelessWidget {
  const _TaskCard({required this.item, required this.accent});
  final Map<String, dynamic> item;
  final bool accent;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    final foreground = accent ? const Color(0xFF10150C) : palette.text;
    return _HoverSurface(
      color: accent ? _Palette.primary : palette.surfaceRaised,
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _friendlyDate(item['due_at']),
            style: TextStyle(color: foreground, fontSize: 11),
          ),
          const SizedBox(height: 7),
          Text(
            _string(item['title'], fallback: 'Planned task'),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: foreground, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          Text(
            _string(item['channel'], fallback: 'local plan'),
            style: TextStyle(
              color: foreground.withValues(alpha: 0.72),
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }
}

class _AgentSummary extends StatelessWidget {
  const _AgentSummary({required this.summary, required this.latestInbox});
  final String summary;
  final Map<String, dynamic> latestInbox;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    return _HoverSurface(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 160,
            width: double.infinity,
            decoration: BoxDecoration(
              color: palette.surfaceRaised,
              borderRadius: BorderRadius.circular(12),
            ),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 58,
                  height: 58,
                  decoration: BoxDecoration(
                    color: palette.surfaceHover,
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: const Text(
                    'A',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
                  ),
                ),
                const Spacer(),
                const Text(
                  'Anuranjan',
                  style: TextStyle(fontWeight: FontWeight.w900),
                ),
                Text(
                  'Local AI companion',
                  style: TextStyle(color: palette.muted, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          const _Eyebrow('SUMMARY'),
          const Text(
            'Inbox at a glance',
            style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 12),
          _SummaryCard(label: 'Email intelligence', value: summary),
          const SizedBox(height: 10),
          _SummaryCard(
            label: 'Latest message',
            value: _string(
              latestInbox['summary'],
              fallback: _string(
                latestInbox['subject'],
                fallback: 'Sync Gmail to build local inbox intelligence.',
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    decoration: BoxDecoration(
      color: _Palette.of(context).surfaceRaised,
      borderRadius: BorderRadius.circular(12),
    ),
    padding: const EdgeInsets.all(13),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(color: _Palette.of(context).muted, fontSize: 11),
        ),
        const SizedBox(height: 5),
        Text(
          value,
          maxLines: 4,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontSize: 13,
            height: 1.45,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    ),
  );
}

class _OverviewDetails extends StatelessWidget {
  const _OverviewDetails({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final graph = _maps(_map(controller.live['stats'])['opportunity_graph']);
    final intelligence = _map(controller.live['intelligence']);
    final suggestions = _maps(intelligence['suggestions']);
    final connectorRuns = _maps(controller.live['connector_runs']);
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth >= 900
            ? (constraints.maxWidth - 32) / 3
            : constraints.maxWidth >= 600
            ? (constraints.maxWidth - 16) / 2
            : constraints.maxWidth;
        return Wrap(
          spacing: 16,
          runSpacing: 16,
          children: [
            SizedBox(
              width: width,
              child: _Panel(
                eyebrow: 'LOCAL AI',
                title: 'Smart Suggestions',
                child: suggestions.isEmpty
                    ? const _Empty('No inbox suggestions need attention.')
                    : Column(
                        children: suggestions
                            .take(5)
                            .map(
                              (item) => _CompactRow(
                                leading: 'AI',
                                title: _string(
                                  item['title'],
                                  fallback: _string(item['summary']),
                                ),
                                subtitle: _string(item['reason']),
                              ),
                            )
                            .toList(),
                      ),
              ),
            ),
            SizedBox(
              width: width,
              child: _Panel(
                eyebrow: 'GRAPH',
                title: 'Opportunity Mix',
                child: graph.isEmpty
                    ? const _Empty('No tracked opportunities yet.')
                    : Column(
                        children: graph
                            .take(6)
                            .map(
                              (item) => _ProgressRow(
                                label: _string(item['label']),
                                value:
                                    (item['percent'] as num?)?.toDouble() ?? 0,
                                trailing: '${item['count'] ?? 0}',
                              ),
                            )
                            .toList(),
                      ),
              ),
            ),
            SizedBox(
              width: width,
              child: _Panel(
                eyebrow: 'PIPELINE HEALTH',
                title: 'Recent Connector Runs',
                child: connectorRuns.isEmpty
                    ? const _Empty('Connector runs will appear after sync.')
                    : Column(
                        children: connectorRuns
                            .take(5)
                            .map(
                              (item) => _CompactRow(
                                leading: _string(
                                  item['status'],
                                  fallback: 'run',
                                ),
                                title: _string(
                                  item['connector'],
                                  fallback: _string(
                                    item['name'],
                                    fallback: 'Local connector',
                                  ),
                                ),
                                subtitle: _string(
                                  item['message'],
                                  fallback: _friendlyDate(item['finished_at']),
                                ),
                              ),
                            )
                            .toList(),
                      ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _OpportunitiesPage extends StatefulWidget {
  const _OpportunitiesPage({required this.controller});
  final AiosController controller;

  @override
  State<_OpportunitiesPage> createState() => _OpportunitiesPageState();
}

class _OpportunitiesPageState extends State<_OpportunitiesPage> {
  final _search = TextEditingController();
  String _filter = 'all';

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final data = controller.dataFor('opportunities');
    final opportunities = data.containsKey('items')
        ? _maps(data['items'])
        : _maps(controller.live['opportunities']);
    final stats = _map(data['stats']);
    final query = _search.text.trim().toLowerCase();
    final visible = opportunities.where((item) {
      final searchable = [
        item['title'],
        item['organization'],
        item['program'],
        item['status'],
        item['kind'],
        item['source'],
        item['notes'],
      ].map(_string).join(' ').toLowerCase();
      if (query.isNotEmpty && !searchable.contains(query)) return false;
      return switch (_filter) {
        'action' => item['needs_action'] == true,
        'deadline' =>
          item['days_left'] is num &&
              (item['days_left'] as num) >= 0 &&
              (item['days_left'] as num) <= 7,
        'wins' => item['is_achievement'] == true,
        _ => true,
      };
    }).toList();

    return _PageColumn(
      children: [
        _Panel(
          eyebrow: 'OPPORTUNITY COMMAND CENTER',
          title: 'Know what deserves your attention.',
          action: _ActionButton(
            label: controller.syncing ? 'Scanning...' : 'Run scan',
            icon: Icons.refresh_rounded,
            onTap: controller.syncing ? null : controller.syncAll,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Selections, applications, assessments, interviews, and build deadlines from your locally synced mail.',
                style: TextStyle(
                  color: _Palette.of(context).muted,
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 18),
              _ActionMetricStrip(
                metrics: [
                  (
                    label: 'Tracked',
                    value: '${stats['total'] ?? opportunities.length}',
                    caption: 'recent signals',
                    icon: Icons.work_outline,
                    color: _Palette.info,
                  ),
                  (
                    label: 'Act now',
                    value:
                        '${stats['action_needed'] ?? opportunities.where((item) => item['needs_action'] == true).length}',
                    caption: 'next steps',
                    icon: Icons.bolt_rounded,
                    color: _Palette.warning,
                  ),
                  (
                    label: 'Due soon',
                    value: '${stats['due_soon'] ?? 0}',
                    caption: 'within 7 days',
                    icon: Icons.event_busy_outlined,
                    color: _Palette.danger,
                  ),
                  (
                    label: 'Wins',
                    value: '${stats['achievements'] ?? 0}',
                    caption: 'selected or shortlisted',
                    icon: Icons.emoji_events_outlined,
                    color: _Palette.success,
                  ),
                ],
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final filters = Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _ActionFilterButton(
                        label: 'All',
                        selected: _filter == 'all',
                        onTap: () => setState(() => _filter = 'all'),
                      ),
                      _ActionFilterButton(
                        label: 'Act now',
                        selected: _filter == 'action',
                        onTap: () => setState(() => _filter = 'action'),
                      ),
                      _ActionFilterButton(
                        label: 'Deadlines',
                        selected: _filter == 'deadline',
                        onTap: () => setState(() => _filter = 'deadline'),
                      ),
                      _ActionFilterButton(
                        label: 'Wins',
                        selected: _filter == 'wins',
                        onTap: () => setState(() => _filter = 'wins'),
                      ),
                    ],
                  );
                  final search = SizedBox(
                    width: constraints.maxWidth < 780
                        ? constraints.maxWidth
                        : 360,
                    child: _WorkspaceSearch(
                      controller: _search,
                      hint: 'Search company, program, stage or source',
                      onChanged: (_) => setState(() {}),
                    ),
                  );
                  if (constraints.maxWidth < 780) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [filters, const SizedBox(height: 12), search],
                    );
                  }
                  return Row(
                    children: [
                      Expanded(child: filters),
                      const SizedBox(width: 16),
                      search,
                    ],
                  );
                },
              ),
              const SizedBox(height: 20),
              _SectionLabel(
                title:
                    '${visible.length} ${visible.length == 1 ? 'opportunity' : 'opportunities'}',
                subtitle: _filter == 'all'
                    ? 'Newest activity first'
                    : 'Filtered to the signals that match this lane',
              ),
              const SizedBox(height: 12),
              if (visible.isEmpty)
                const _Empty('No opportunity matches this search or filter.')
              else
                ...visible.indexed.map(
                  (entry) => _Reveal(
                    index: entry.$1,
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _OpportunityRow(
                        item: entry.$2,
                        onOpen: () => _showOpportunity(context, entry.$2),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  void _showOpportunity(BuildContext context, Map<String, dynamic> item) {
    showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 680, maxHeight: 720),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const _Eyebrow('OPPORTUNITY DETAILS'),
                            Text(
                              _string(
                                item['program'],
                                fallback: _string(
                                  item['organization'],
                                  fallback: 'Opportunity',
                                ),
                              ),
                              style: const TextStyle(
                                fontSize: 25,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              _string(item['title']),
                              style: TextStyle(
                                color: _Palette.of(context).muted,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        tooltip: 'Close details',
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(Icons.close_rounded),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      _SignalPill(
                        _string(item['status'], fallback: 'Tracking'),
                        _opportunityTone(item),
                      ),
                      _MetaPill(_string(item['kind'], fallback: 'opportunity')),
                      if (_string(item['deadline_message']).isNotEmpty)
                        _SignalPill(
                          _string(item['deadline_message']),
                          _Palette.warning,
                        ),
                    ],
                  ),
                  const SizedBox(height: 22),
                  const _SectionLabel(
                    title: 'Next move',
                    subtitle:
                        'The clearest action AiOS can infer from this signal',
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _string(
                      item['next_action'],
                      fallback:
                          'Review the latest update and decide the next step.',
                    ),
                    style: const TextStyle(
                      fontSize: 16,
                      height: 1.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 22),
                  const _SectionLabel(
                    title: 'Local summary',
                    subtitle:
                        'Derived from synchronized mail; raw content stays on this device',
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _string(
                      item['notes'],
                      fallback: 'No summary is available yet.',
                    ),
                    style: const TextStyle(height: 1.55),
                  ),
                  const SizedBox(height: 20),
                  _KeyValue(
                    'Source',
                    _string(item['source'], fallback: 'Local intelligence'),
                  ),
                  _KeyValue('Updated', _friendlyDate(item['updated_at'])),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _OpportunityRow extends StatelessWidget {
  const _OpportunityRow({required this.item, required this.onOpen});
  final Map<String, dynamic> item;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final title = _string(
      item['program'],
      fallback: _string(item['organization'], fallback: 'Opportunity'),
    );
    return _HoverSurface(
      color: _Palette.of(context).surfaceRaised,
      borderColor: item['needs_action'] == true
          ? _opportunityTone(item).withValues(alpha: 0.5)
          : null,
      padding: const EdgeInsets.all(16),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final content = Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: _opportunityTone(item).withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(
                  _opportunityIcon(item),
                  color: _opportunityTone(item),
                  size: 21,
                ),
              ),
              const SizedBox(width: 13),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Text(
                            title,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        _SignalPill(
                          _string(item['status'], fallback: 'Tracking'),
                          _opportunityTone(item),
                        ),
                      ],
                    ),
                    const SizedBox(height: 5),
                    Text(
                      _string(item['title']),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: _Palette.of(context).muted,
                        fontSize: 12,
                        height: 1.35,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 7,
                      children: [
                        _MetaPill(
                          _string(item['kind'], fallback: 'opportunity'),
                        ),
                        if (_string(item['source']).isNotEmpty)
                          _MetaPill(_string(item['source'])),
                        if (item['days_left'] is num)
                          _SignalPill(
                            _shortDeadline(item),
                            _deadlineTone(item),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _string(
                        item['next_action'],
                        fallback:
                            'Review the latest update and decide the next step.',
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        height: 1.45,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          );
          final details = _ActionButton(
            label: 'Details',
            icon: Icons.arrow_forward_rounded,
            onTap: onOpen,
          );
          if (constraints.maxWidth < 690) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                content,
                const SizedBox(height: 14),
                Align(alignment: Alignment.centerRight, child: details),
              ],
            );
          }
          return Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(child: content),
              const SizedBox(width: 18),
              details,
            ],
          );
        },
      ),
    );
  }
}

class _RemindersPage extends StatefulWidget {
  const _RemindersPage({required this.controller});
  final AiosController controller;

  @override
  State<_RemindersPage> createState() => _RemindersPageState();
}

class _RemindersPageState extends State<_RemindersPage> {
  String _filter = 'open';

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final data = controller.dataFor('reminders');
    final reminders = data.containsKey('items')
        ? _maps(data['items'])
        : _maps(controller.live['reminders']);
    final stats = _map(data['stats']);
    final visible = reminders
        .where(
          (item) => switch (_filter) {
            'unread' => item['is_read'] != true,
            'overdue' => item['urgency'] == 'overdue',
            _ => true,
          },
        )
        .toList();
    return _PageColumn(
      children: [
        _Panel(
          eyebrow: 'ACTION CENTER · LATEST 100 EMAILS PER ACCOUNT',
          title: 'Clear reminders, not vague alerts.',
          action: _ActionButton(
            label: controller.syncing ? 'Scanning...' : 'Refresh tasks',
            icon: Icons.refresh_rounded,
            onTap: controller.syncing ? null : controller.syncAll,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Each card explains what is due, why it matters now, and which Gmail account produced the task.',
                style: TextStyle(
                  color: _Palette.of(context).muted,
                  height: 1.45,
                ),
              ),
              const SizedBox(height: 18),
              _ActionMetricStrip(
                metrics: [
                  (
                    label: 'Open',
                    value: '${stats['open'] ?? reminders.length}',
                    caption: 'tasks due now',
                    icon: Icons.task_alt_outlined,
                    color: _Palette.info,
                  ),
                  (
                    label: 'Overdue',
                    value:
                        '${stats['overdue'] ?? reminders.where((item) => item['urgency'] == 'overdue').length}',
                    caption: 'need a decision',
                    icon: Icons.warning_amber_rounded,
                    color: _Palette.danger,
                  ),
                  (
                    label: 'Unread',
                    value:
                        '${stats['unread'] ?? reminders.where((item) => item['is_read'] != true).length}',
                    caption: 'unacknowledged',
                    icon: Icons.mark_email_unread_outlined,
                    color: _Palette.warning,
                  ),
                  (
                    label: 'Completed',
                    value: '${stats['completed_today'] ?? 0}',
                    caption: 'today',
                    icon: Icons.done_all_rounded,
                    color: _Palette.success,
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _ActionFilterButton(
                    label: 'Open',
                    selected: _filter == 'open',
                    onTap: () => setState(() => _filter = 'open'),
                  ),
                  _ActionFilterButton(
                    label: 'Unread',
                    selected: _filter == 'unread',
                    onTap: () => setState(() => _filter = 'unread'),
                  ),
                  _ActionFilterButton(
                    label: 'Overdue',
                    selected: _filter == 'overdue',
                    onTap: () => setState(() => _filter = 'overdue'),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _SectionLabel(
                title:
                    '${visible.length} ${visible.length == 1 ? 'task' : 'tasks'} in this lane',
                subtitle:
                    'Mark read acknowledges an alert. Complete task closes the source email task and planner row.',
              ),
              const SizedBox(height: 12),
              if (visible.isEmpty)
                const _Empty('Nothing needs attention in this lane.')
              else
                ...visible.indexed.map(
                  (entry) => _Reveal(
                    index: entry.$1,
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _ReminderRow(
                        item: entry.$2,
                        controller: controller,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ReminderRow extends StatelessWidget {
  const _ReminderRow({required this.item, required this.controller});

  final Map<String, dynamic> item;
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final id = (item['id'] as num?)?.toInt();
    final busy = id != null && controller.isActionBusy('reminder:$id');
    final tone = _reminderTone(item);
    return _HoverSurface(
      color: _Palette.of(context).surfaceRaised,
      borderColor: tone.withValues(alpha: 0.48),
      padding: const EdgeInsets.all(15),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final stackActions = constraints.maxWidth < 660;
          final actions = Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (item['is_read'] != true)
                _ActionButton(
                  label: 'Mark read',
                  icon: Icons.mark_email_read_outlined,
                  onTap: id == null || busy
                      ? null
                      : () => controller.updateReminder(id, done: false),
                ),
              if (item['is_read'] == true)
                const _SignalPill('Read', _Palette.success),
              _ActionButton(
                label: busy ? 'Saving...' : 'Complete task',
                icon: Icons.check_rounded,
                primary: true,
                onTap: id == null || busy
                    ? null
                    : () => controller.updateReminder(id, done: true),
              ),
            ],
          );
          final details = Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: tone.withValues(alpha: 0.14),
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Icon(_reminderIcon(item), size: 19, color: tone),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _string(item['title'], fallback: 'Reminder'),
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Wrap(
                      spacing: 8,
                      runSpacing: 7,
                      children: [
                        _SignalPill(
                          _string(
                            item['due_label'],
                            fallback: _friendlyDate(item['due_at']),
                          ),
                          tone,
                        ),
                        _MetaPill(
                          _string(item['priority'], fallback: 'normal'),
                        ),
                        _MetaPill(_string(item['source'], fallback: 'Local')),
                      ],
                    ),
                    if (_string(item['email_subject']).isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Text(
                        _string(item['email_subject']),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontWeight: FontWeight.w700,
                          height: 1.4,
                        ),
                      ),
                    ],
                    if (_string(item['context']).isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        _string(item['context']),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: _Palette.of(context).muted,
                          fontSize: 11,
                          height: 1.35,
                        ),
                      ),
                    ],
                    const SizedBox(height: 10),
                    Text(
                      _string(
                        item['why'],
                        fallback:
                            'Review this task and decide the next action.',
                      ),
                      style: TextStyle(
                        color: tone,
                        fontSize: 12,
                        height: 1.4,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          );
          if (stackActions) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [details, const SizedBox(height: 12), actions],
            );
          }
          return Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(child: details),
              const SizedBox(width: 16),
              actions,
            ],
          );
        },
      ),
    );
  }
}

class _InboxPage extends StatelessWidget {
  const _InboxPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final items = _maps(controller.live['inbox_items']);
    return _PageColumn(
      children: [
        _Panel(
          eyebrow: 'CLASSIFIER',
          title: 'Recent Inbox Intelligence',
          action: _ActionButton(
            label: controller.syncing ? 'Syncing...' : 'Sync inbox',
            icon: Icons.sync_rounded,
            onTap: controller.syncing ? null : controller.syncAll,
          ),
          child: items.isEmpty
              ? const _Empty('Classified emails will appear here.')
              : Column(
                  children: items.indexed.map((entry) {
                    final item = entry.$2;
                    final confidence =
                        ((item['confidence'] as num?)?.toDouble() ?? 0) * 100;
                    return _Reveal(
                      index: entry.$1,
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _HoverSurface(
                          color: _Palette.of(context).surfaceRaised,
                          padding: const EdgeInsets.all(16),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                width: 48,
                                height: 36,
                                decoration: BoxDecoration(
                                  color: const Color(0x1F75D7FF),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  '${confidence.round()}%',
                                  style: const TextStyle(
                                    color: _Palette.info,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 13),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      _string(
                                        item['subject'],
                                        fallback: 'Email',
                                      ),
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w900,
                                      ),
                                    ),
                                    const SizedBox(height: 5),
                                    Text(
                                      '${_string(item['category'])} - ${_string(item['sender'], fallback: 'Local inbox')}',
                                      style: TextStyle(
                                        color: _Palette.of(context).muted,
                                        fontSize: 12,
                                      ),
                                    ),
                                    if (_string(
                                      item['summary'],
                                    ).isNotEmpty) ...[
                                      const SizedBox(height: 9),
                                      Text(
                                        _string(item['summary']),
                                        maxLines: 4,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(height: 1.5),
                                      ),
                                    ],
                                    if (_string(
                                      item['next_action'],
                                    ).isNotEmpty) ...[
                                      const SizedBox(height: 8),
                                      Text(
                                        'Next: ${_string(item['next_action'])}',
                                        style: const TextStyle(
                                          color: _Palette.primary,
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
        ),
      ],
    );
  }
}

class _MemoryPage extends StatefulWidget {
  const _MemoryPage({required this.controller});
  final AiosController controller;

  @override
  State<_MemoryPage> createState() => _MemoryPageState();
}

class _MemoryPageState extends State<_MemoryPage> {
  final _query = TextEditingController();

  @override
  void dispose() {
    _query.dispose();
    super.dispose();
  }

  Future<void> _showMemoryForm({
    required String title,
    required List<({String key, String label, bool multiline})> fields,
    required Future<bool> Function(Map<String, String>) onSave,
  }) async {
    final values = {
      for (final field in fields) field.key: TextEditingController(),
    };
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: _Palette.of(context).surface,
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
        content: SizedBox(
          width: 520,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: fields
                  .map(
                    (field) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: TextField(
                        controller: values[field.key],
                        minLines: field.multiline ? 3 : 1,
                        maxLines: field.multiline ? 6 : 1,
                        decoration: InputDecoration(
                          labelText: field.label,
                          border: const OutlineInputBorder(),
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: widget.controller.memoryBusy
                ? null
                : () async {
                    final payload = {
                      for (final entry in values.entries)
                        entry.key: entry.value.text.trim(),
                    };
                    final saved = await onSave(payload);
                    if (saved && dialogContext.mounted) {
                      Navigator.pop(dialogContext);
                    }
                  },
            child: const Text('Save locally'),
          ),
        ],
      ),
    );
    for (final controller in values.values) {
      controller.dispose();
    }
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    final data = controller.dataFor('memory');
    final counts = _map(data['counts']);
    final projects = _maps(data['projects']);
    final entities = _maps(data['entities']);
    final recentFacts = _maps(data['recent_facts']);
    return _WorkspacePage(
      eyebrow: 'PERSISTENT PERSONAL MEMORY',
      title: 'Continue where you stopped.',
      subtitle:
          'Ask what you were doing, restore project context, and save checkpoints without losing history.',
      actions: [
        _ActionButton(
          label: 'New entity',
          onTap: () => _showMemoryForm(
            title: 'Create memory entity',
            fields: const [
              (key: 'name', label: 'Name', multiline: false),
              (
                key: 'entity_type',
                label: 'Type (project, goal, skill)',
                multiline: false,
              ),
              (key: 'status', label: 'Status', multiline: false),
              (key: 'summary', label: 'Summary', multiline: true),
            ],
            onSave: (value) => controller.createMemoryEntity(
              entityType: value['entity_type']!.isEmpty
                  ? 'project'
                  : value['entity_type']!,
              name: value['name']!,
              status: value['status']!.isEmpty ? 'active' : value['status']!,
              summary: value['summary']!,
            ),
          ),
        ),
        _ActionButton(
          label: 'Save note',
          onTap: () => _showMemoryForm(
            title: 'Remember a note',
            fields: const [
              (
                key: 'entity_name',
                label: 'Related entity (optional)',
                multiline: false,
              ),
              (key: 'entity_type', label: 'Entity type', multiline: false),
              (
                key: 'content',
                label: 'What should AiOS remember?',
                multiline: true,
              ),
            ],
            onSave: (value) => controller.saveMemoryNote(
              entityName: value['entity_name']!,
              entityType: value['entity_type']!.isEmpty
                  ? 'project'
                  : value['entity_type']!,
              content: value['content']!,
            ),
          ),
        ),
        _ActionButton(
          label: 'Save checkpoint',
          primary: true,
          onTap: () => _showMemoryForm(
            title: 'Save project checkpoint',
            fields: const [
              (key: 'project_name', label: 'Project name', multiline: false),
              (key: 'summary', label: 'Where you stopped', multiline: true),
              (
                key: 'open_files',
                label: 'Open files (comma or line separated)',
                multiline: true,
              ),
              (key: 'active_tasks', label: 'Active tasks', multiline: true),
              (key: 'next_actions', label: 'Next actions', multiline: true),
              (key: 'notes', label: 'Notes', multiline: true),
            ],
            onSave: (value) => controller.saveMemoryCheckpoint(
              projectName: value['project_name']!,
              summary: value['summary']!,
              openFiles: value['open_files']!,
              activeTasks: value['active_tasks']!,
              nextActions: value['next_actions']!,
              notes: value['notes']!,
            ),
          ),
        ),
      ],
      child: Column(
        children: [
          _Panel(
            eyebrow: 'ASK LOCAL MEMORY',
            title: 'What were you doing?',
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _query,
                    onSubmitted: controller.askMemory,
                    decoration: const InputDecoration(
                      hintText: 'What was I doing yesterday?',
                      prefixIcon: Icon(Icons.search_rounded),
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                _ActionButton(
                  label: controller.memoryBusy ? 'Searching...' : 'Ask Memory',
                  primary: true,
                  onTap: controller.memoryBusy
                      ? null
                      : () => controller.askMemory(_query.text),
                ),
              ],
            ),
          ),
          if (controller.memoryAnswer != null) ...[
            const SizedBox(height: 16),
            _MemoryAnswer(answer: controller.memoryAnswer!),
          ],
          const SizedBox(height: 16),
          _SmallMetricRow(
            values: [
              ('Projects', '${counts['projects'] ?? 0}'),
              ('Entities', '${counts['entities'] ?? 0}'),
              ('Memories', '${counts['facts'] ?? 0}'),
              ('Relations', '${counts['relations'] ?? 0}'),
            ],
          ),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (context, constraints) {
              final wide = constraints.maxWidth >= 820;
              final projectPanel = _Panel(
                eyebrow: 'RESTORE CONTEXT',
                title: 'Active projects',
                child: projects.isEmpty
                    ? const _Empty('Save a checkpoint to resume work quickly.')
                    : Column(
                        children: projects
                            .take(12)
                            .map((item) => _MemoryProjectCard(item: item))
                            .toList(),
                      ),
              );
              final contextPanels = Column(
                children: [
                  _Panel(
                    eyebrow: 'KNOWLEDGE GRAPH',
                    title: 'Connected context',
                    child: entities.isEmpty
                        ? const _Empty('No connected entities yet.')
                        : Column(
                            children: entities
                                .take(12)
                                .map(
                                  (item) => _ListRow(
                                    icon: Icons.hub_outlined,
                                    title: _string(
                                      item['name'],
                                      fallback: 'Entity',
                                    ),
                                    subtitle: _string(item['summary']),
                                    meta: _string(item['entity_type']),
                                  ),
                                )
                                .toList(),
                          ),
                  ),
                  const SizedBox(height: 16),
                  _Panel(
                    eyebrow: 'RECENT',
                    title: 'Saved memories',
                    child: recentFacts.isEmpty
                        ? const _Empty('Notes you save will stay here.')
                        : Column(
                            children: recentFacts
                                .take(8)
                                .map(
                                  (item) => _ListRow(
                                    icon: Icons.notes_rounded,
                                    title: _string(
                                      item['content'],
                                      fallback: 'Memory',
                                    ),
                                    subtitle: _string(item['source']),
                                    meta: _string(item['fact_type']),
                                  ),
                                )
                                .toList(),
                          ),
                  ),
                ],
              );
              if (!wide) {
                return Column(
                  children: [
                    projectPanel,
                    const SizedBox(height: 16),
                    contextPanels,
                  ],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 6, child: projectPanel),
                  const SizedBox(width: 16),
                  Expanded(flex: 5, child: contextPanels),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _MemoryAnswer extends StatelessWidget {
  const _MemoryAnswer({required this.answer});
  final Map<String, dynamic> answer;

  @override
  Widget build(BuildContext context) {
    final results = _maps(answer['results']);
    return _Panel(
      eyebrow: 'RECALLED LOCALLY',
      title: _string(answer['answer'], fallback: 'Memory result'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_string(answer['suggestion']).isNotEmpty)
            Text(
              _string(answer['suggestion']),
              style: TextStyle(color: _Palette.of(context).muted),
            ),
          if (results.isNotEmpty) ...[
            const SizedBox(height: 12),
            ...results.take(5).map((result) {
              final entity = _map(result['entity']);
              final fact = _map(result['fact']);
              return _ListRow(
                icon: Icons.auto_awesome_outlined,
                title: _string(
                  entity['name'],
                  fallback: _string(
                    fact['content'],
                    fallback: 'Related memory',
                  ),
                ),
                subtitle: _string(
                  fact['content'],
                  fallback: _string(entity['summary']),
                ),
                meta: _string(result['kind']),
              );
            }),
          ],
        ],
      ),
    );
  }
}

class _MemoryProjectCard extends StatelessWidget {
  const _MemoryProjectCard({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final checkpoint = _map(item['latest_checkpoint']);
    final nextActions = _strings(checkpoint['next_actions']);
    final activeTasks = _strings(checkpoint['active_tasks']);
    final openFiles = _strings(checkpoint['open_files']);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: _HoverSurface(
        color: _Palette.of(context).surfaceRaised,
        padding: const EdgeInsets.all(15),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    _string(item['name'], fallback: 'Project'),
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                ),
                _MetaPill(_string(item['status'], fallback: 'active')),
              ],
            ),
            const SizedBox(height: 7),
            Text(
              _string(
                checkpoint['summary'],
                fallback: _string(
                  item['summary'],
                  fallback: 'No checkpoint summary yet.',
                ),
              ),
              style: TextStyle(color: _Palette.of(context).muted, height: 1.45),
            ),
            if (nextActions.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                'Next: ${nextActions.join(' | ')}',
                style: const TextStyle(
                  color: _Palette.primary,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
            if (activeTasks.isNotEmpty) ...[
              const SizedBox(height: 7),
              Text('Active: ${activeTasks.join(' | ')}'),
            ],
            if (openFiles.isNotEmpty) ...[
              const SizedBox(height: 7),
              Text(
                'Files: ${openFiles.join(' | ')}',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: _Palette.of(context).muted,
                  fontSize: 12,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SourcesPage extends StatelessWidget {
  const _SourcesPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final accounts = _maps(controller.accounts['accounts']);
    final google = _map(controller.accounts['google_client']);
    return _WorkspacePage(
      eyebrow: 'PRIVATE DATA SOURCES',
      title: 'Sources',
      subtitle:
          'Connect Gmail once in your browser; AiOS stores the connection locally until you remove it.',
      actions: [
        _ActionButton(
          label: controller.signIn == null
              ? 'Login with Google'
              : 'Signing in...',
          icon: Icons.login_rounded,
          primary: true,
          onTap: controller.signIn == null ? controller.connectGoogle : null,
        ),
      ],
      child: Column(
        children: [
          if (controller.signIn != null) ...[
            _SignInPanel(controller: controller),
            const SizedBox(height: 16),
          ],
          _Panel(
            eyebrow: 'GMAIL READ ONLY',
            title: 'Connected accounts',
            action: Text(
              '${accounts.length} connected',
              style: const TextStyle(
                color: _Palette.primary,
                fontWeight: FontWeight.w900,
              ),
            ),
            child: accounts.isEmpty
                ? _Empty(
                    google['configured'] == true
                        ? 'No Gmail account is connected yet.'
                        : 'Google login needs its desktop OAuth client configuration.',
                  )
                : Column(
                    children: accounts
                        .map(
                          (item) =>
                              _AccountRow(item: item, controller: controller),
                        )
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _SignInPanel extends StatelessWidget {
  const _SignInPanel({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final signIn = controller.signIn ?? const {};
    return _Panel(
      eyebrow: 'GOOGLE SIGN IN',
      title: 'Continue in your browser',
      child: Column(
        children: [
          const SizedBox(
            width: 34,
            height: 34,
            child: CircularProgressIndicator(
              strokeWidth: 3,
              color: _Palette.primary,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            _string(
              signIn['message'],
              fallback: 'Waiting for Google sign-in to complete...',
            ),
            textAlign: TextAlign.center,
            style: TextStyle(color: _Palette.of(context).muted),
          ),
          const SizedBox(height: 16),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 10,
            runSpacing: 10,
            children: [
              _ActionButton(
                label: 'Continue in browser',
                icon: Icons.open_in_browser_rounded,
                primary: true,
                onTap: controller.continueGoogleSignIn,
              ),
              _ActionButton(
                label: 'Cancel sign in',
                icon: Icons.close_rounded,
                onTap: controller.cancelGoogleSignIn,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AccountRow extends StatelessWidget {
  const _AccountRow({required this.item, required this.controller});
  final Map<String, dynamic> item;
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final id = (item['id'] as num?)?.toInt();
    final busy = id != null && controller.isActionBusy('account:$id');
    final syncEnabled = item['sync_enabled'] != false;
    final label = _string(item['label']);
    final email = _string(item['email'], fallback: 'Google account');
    final customLabel =
        label.isNotEmpty && label.toLowerCase() != email.toLowerCase()
        ? label
        : '';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: _HoverSurface(
        color: _Palette.of(context).surfaceRaised,
        padding: const EdgeInsets.all(15),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final stackActions = constraints.maxWidth < 720;
            final identity = Row(
              children: [
                Container(
                  width: 42,
                  height: 42,
                  decoration: const BoxDecoration(
                    color: Color(0x1FA7FF3C),
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: const Icon(
                    Icons.mail_outline,
                    color: _Palette.primary,
                  ),
                ),
                const SizedBox(width: 13),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        customLabel.isEmpty ? email : customLabel,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                      if (customLabel.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          email,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: _Palette.of(context).muted,
                            fontSize: 12,
                          ),
                        ),
                      ],
                      const SizedBox(height: 3),
                      Text(
                        _string(
                          item['last_sync_at'],
                          fallback: 'Connected locally',
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: _Palette.of(context).muted,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            );
            final controls = Wrap(
              spacing: 4,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                _MetaPill(syncEnabled ? 'Sync on' : 'Paused'),
                IconButton(
                  tooltip: 'Rename account',
                  onPressed: id == null || busy
                      ? null
                      : () => _renameAccount(context, item, controller),
                  icon: const Icon(Icons.edit_outlined),
                ),
                IconButton(
                  tooltip: syncEnabled ? 'Pause sync' : 'Resume sync',
                  onPressed: id == null || busy
                      ? null
                      : () => controller.updateAccount(
                          id,
                          syncEnabled: !syncEnabled,
                        ),
                  icon: Icon(
                    syncEnabled
                        ? Icons.pause_circle_outline
                        : Icons.play_circle_outline,
                  ),
                ),
                IconButton(
                  tooltip: 'Sync account',
                  onPressed: id == null || controller.syncing || busy
                      ? null
                      : () => controller.syncAccount(id),
                  icon: const Icon(Icons.sync),
                ),
                IconButton(
                  tooltip: 'Disconnect account',
                  onPressed: id == null || busy
                      ? null
                      : () => _confirmAccountRemoval(
                          context,
                          id,
                          email,
                          controller,
                        ),
                  icon: const Icon(Icons.link_off_outlined),
                ),
              ],
            );
            if (stackActions) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [identity, const SizedBox(height: 12), controls],
              );
            }
            return Row(
              children: [
                Expanded(child: identity),
                const SizedBox(width: 14),
                controls,
              ],
            );
          },
        ),
      ),
    );
  }
}

Future<void> _renameAccount(
  BuildContext context,
  Map<String, dynamic> item,
  AiosController controller,
) async {
  final id = (item['id'] as num?)?.toInt();
  if (id == null) return;
  final field = TextEditingController(text: _string(item['label']));
  final label = await showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Rename Gmail account'),
      content: TextField(
        controller: field,
        autofocus: true,
        decoration: const InputDecoration(
          labelText: 'Account name',
          hintText: 'College, Personal, Work...',
        ),
        onSubmitted: (value) => Navigator.pop(context, value.trim()),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, field.text.trim()),
          child: const Text('Save name'),
        ),
      ],
    ),
  );
  field.dispose();
  if (label != null) await controller.updateAccount(id, label: label);
}

Future<void> _confirmAccountRemoval(
  BuildContext context,
  int id,
  String email,
  AiosController controller,
) async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Disconnect Gmail account?'),
      content: Text(
        '$email will stop syncing. Locally analyzed history stays on this device.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Keep connected'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Disconnect'),
        ),
      ],
    ),
  );
  if (confirmed == true) await controller.removeAccount(id);
}

class _ConnectorsPage extends StatelessWidget {
  const _ConnectorsPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final connectors = _maps(controller.dataFor('connectors')['items']);
    return _WorkspacePage(
      eyebrow: 'LIVE PIPELINES',
      title: 'Connectors',
      subtitle:
          'Local sync pipelines for mail, reminders, jobs, and hackathon intelligence.',
      actions: [
        _ActionButton(
          label: controller.syncing ? 'Syncing...' : 'Sync Gmail',
          icon: Icons.sync_rounded,
          primary: true,
          onTap: controller.syncing ? null : controller.syncAll,
        ),
      ],
      child: _Panel(
        eyebrow: 'AVAILABLE',
        title: 'Connector status',
        child: connectors.isEmpty
            ? const _Empty('Connector status is loading.')
            : Column(
                children: connectors
                    .map(
                      (item) => _ServiceActionRow(
                        icon: item['configured'] == true
                            ? Icons.check_circle_outline
                            : Icons.info_outline,
                        title: _string(item['name'], fallback: 'Connector'),
                        subtitle: [
                          _string(item['description']),
                          _string(item['setup']),
                        ].where((value) => value.isNotEmpty).join('\n'),
                        meta: item['configured'] == true
                            ? 'Configured'
                            : 'Needs setup',
                        actionLabel:
                            controller.isActionBusy(
                              'connector:${_string(item['id'])}',
                            )
                            ? 'Running...'
                            : 'Run',
                        actionIcon: Icons.play_arrow_rounded,
                        onAction:
                            _string(item['id']).isEmpty ||
                                controller.isActionBusy(
                                  'connector:${_string(item['id'])}',
                                )
                            ? null
                            : () =>
                                  controller.runConnector(_string(item['id'])),
                      ),
                    )
                    .toList(),
              ),
      ),
    );
  }
}

class _WorkersPage extends StatelessWidget {
  const _WorkersPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) => _WorkspacePage(
    eyebrow: 'BACKGROUND CORE',
    title: 'Workers',
    subtitle:
        'Native background services continue securely while the window is hidden in the tray.',
    child: _Panel(
      eyebrow: 'LOCAL SERVICES',
      title:
          '${controller.workers.where((item) => _map(item)['running'] == true).length} of ${controller.workers.length} running',
      child: controller.workers.isEmpty
          ? const _Empty('Worker status is loading.')
          : Column(
              children: controller.workers.map((raw) {
                final item = _map(raw);
                final id = _string(item['id']);
                final running = item['running'] == true;
                final busy = controller.isActionBusy('worker:$id');
                return _ServiceActionRow(
                  icon: item['running'] == true
                      ? Icons.play_circle_outline
                      : Icons.pause_circle_outline,
                  title: _string(item['name'], fallback: 'Worker'),
                  subtitle: _string(item['description']),
                  meta: running ? 'Running' : 'Stopped',
                  actionLabel: busy
                      ? 'Updating...'
                      : running
                      ? 'Stop'
                      : 'Start',
                  actionIcon: running
                      ? Icons.stop_circle_outlined
                      : Icons.play_arrow_rounded,
                  onAction: id.isEmpty || busy
                      ? null
                      : () =>
                            controller.setWorkerRunning(id, running: !running),
                );
              }).toList(),
            ),
    ),
  );
}

class _SettingsPage extends StatelessWidget {
  const _SettingsPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final startup = _map(controller.desktop['startup']);
    return _WorkspacePage(
      eyebrow: 'LOCAL CONTROL',
      title: 'Settings',
      subtitle:
          'Control appearance, Windows startup, tray behavior, and the private local runtime.',
      child: Column(
        children: [
          _Panel(
            eyebrow: 'RUNTIME',
            title: 'Native Windows app',
            child: Column(
              children: [
                _KeyValue('Client', 'Flutter native Windows'),
                _KeyValue(
                  'Core API',
                  controller.api.baseUrl.isEmpty
                      ? 'Starting'
                      : controller.api.baseUrl,
                ),
                _KeyValue(
                  'Local data',
                  _string(controller.desktop['data_dir']),
                ),
                _KeyValue('Status', controller.message),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _Panel(
            eyebrow: 'APPLICATION',
            title: 'Window behavior',
            child: Column(
              children: [
                _SettingToggle(
                  icon: Icons.dark_mode_outlined,
                  title: 'Dark mode',
                  subtitle:
                      'Keep the original AiOS high-contrast workspace theme.',
                  value: controller.darkMode,
                  onChanged: (_) => controller.toggleTheme(),
                ),
                _SettingToggle(
                  icon: Icons.rocket_launch_outlined,
                  title: 'Open on Windows startup',
                  subtitle: 'Start quietly in the system tray after sign-in.',
                  value: startup['enabled'] == true,
                  onChanged: (value) => controller.setStartup(
                    enabled: value,
                    background: startup['background'] != false,
                  ),
                ),
                _SettingToggle(
                  icon: Icons.visibility_off_outlined,
                  title: 'Start minimized in tray',
                  subtitle:
                      'Keep the workspace hidden when AiOS starts with Windows.',
                  value: startup['background'] != false,
                  onChanged: (value) => controller.setStartup(
                    enabled: startup['enabled'] == true,
                    background: value,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: _ActionButton(
                        label: 'Hide to tray',
                        icon: Icons.keyboard_arrow_down_rounded,
                        onTap: controller.hideToTray,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _ActionButton(
                        label: 'Exit AiOS',
                        icon: Icons.power_settings_new_rounded,
                        danger: true,
                        onTap: controller.exitApp,
                      ),
                    ),
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

class _WorkspacePage extends StatelessWidget {
  const _WorkspacePage({
    required this.eyebrow,
    required this.title,
    required this.subtitle,
    required this.child,
    this.actions = const [],
  });
  final String eyebrow;
  final String title;
  final String subtitle;
  final Widget child;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final stackHeader = constraints.maxWidth < 760;
      final copy = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Eyebrow(eyebrow),
          Text(
            title,
            style: TextStyle(
              fontSize: stackHeader ? 34 : 40,
              height: 1.1,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            subtitle,
            style: TextStyle(color: _Palette.of(context).muted, height: 1.5),
          ),
        ],
      );
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(2, 10, 2, 20),
            child: stackHeader
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      copy,
                      if (actions.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        Wrap(spacing: 10, runSpacing: 10, children: actions),
                      ],
                    ],
                  )
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Expanded(child: copy),
                      if (actions.isNotEmpty) ...[
                        const SizedBox(width: 18),
                        Flexible(
                          child: Wrap(
                            alignment: WrapAlignment.end,
                            spacing: 10,
                            runSpacing: 10,
                            children: actions,
                          ),
                        ),
                      ],
                    ],
                  ),
          ),
          child,
        ],
      );
    },
  );
}

class _PageColumn extends StatelessWidget {
  const _PageColumn({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: children,
  );
}

class _Panel extends StatelessWidget {
  const _Panel({
    required this.title,
    required this.child,
    this.eyebrow = '',
    this.action,
  });
  final String title;
  final String eyebrow;
  final Widget child;
  final Widget? action;

  @override
  Widget build(BuildContext context) => _HoverSurface(
    padding: const EdgeInsets.all(20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final heading = Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (eyebrow.isNotEmpty) _Eyebrow(eyebrow),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 19,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            );
            if (action == null) return heading;
            if (constraints.maxWidth < 560) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  heading,
                  const SizedBox(height: 12),
                  Align(alignment: Alignment.centerLeft, child: action),
                ],
              );
            }
            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: heading),
                const SizedBox(width: 12),
                action!,
              ],
            );
          },
        ),
        const SizedBox(height: 16),
        child,
      ],
    ),
  );
}

class _HoverSurface extends StatefulWidget {
  const _HoverSurface({
    required this.child,
    this.color,
    this.borderColor,
    this.padding = EdgeInsets.zero,
    this.height,
  });
  final Widget child;
  final Color? color;
  final Color? borderColor;
  final EdgeInsets padding;
  final double? height;

  @override
  State<_HoverSurface> createState() => _HoverSurfaceState();
}

class _HoverSurfaceState extends State<_HoverSurface> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 240),
        curve: const Cubic(0.2, 0.8, 0.2, 1),
        height: widget.height,
        transform: Matrix4.translationValues(0, _hovered ? -3 : 0, 0),
        decoration: BoxDecoration(
          color: widget.color ?? palette.surface,
          border: Border.all(
            color:
                widget.borderColor ??
                (_hovered ? palette.borderStrong : palette.border),
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: _hovered
              ? const [
                  BoxShadow(
                    color: Color(0x3D000000),
                    blurRadius: 32,
                    offset: Offset(0, 12),
                  ),
                ]
              : const [],
        ),
        padding: widget.padding,
        child: widget.child,
      ),
    );
  }
}

class _Reveal extends StatefulWidget {
  const _Reveal({required this.index, required this.child});
  final int index;
  final Widget child;

  @override
  State<_Reveal> createState() => _RevealState();
}

class _RevealState extends State<_Reveal> {
  bool _visible = false;

  @override
  void initState() {
    super.initState();
    Timer(Duration(milliseconds: (widget.index * 42).clamp(0, 294)), () {
      if (mounted) setState(() => _visible = true);
    });
  }

  @override
  Widget build(BuildContext context) => AnimatedOpacity(
    opacity: _visible ? 1 : 0,
    duration: const Duration(milliseconds: 420),
    curve: const Cubic(0.2, 0.8, 0.2, 1),
    child: AnimatedSlide(
      offset: _visible ? Offset.zero : const Offset(0, 0.08),
      duration: const Duration(milliseconds: 420),
      curve: const Cubic(0.2, 0.8, 0.2, 1),
      child: widget.child,
    ),
  );
}

class _ListRow extends StatelessWidget {
  const _ListRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    this.meta = '',
  });
  final IconData icon;
  final String title;
  final String subtitle;
  final String meta;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: _HoverSurface(
      color: _Palette.of(context).surfaceRaised,
      padding: const EdgeInsets.all(15),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 520;
          final copy = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
              if (subtitle.isNotEmpty) ...[
                const SizedBox(height: 5),
                Text(
                  subtitle,
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: _Palette.of(context).muted,
                    fontSize: 12,
                    height: 1.5,
                  ),
                ),
              ],
              if (compact && meta.isNotEmpty) ...[
                const SizedBox(height: 10),
                _MetaPill(meta),
              ],
            ],
          );
          return Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: _Palette.of(context).surfaceHover,
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Icon(icon, size: 19, color: _Palette.primary),
              ),
              const SizedBox(width: 12),
              Expanded(child: copy),
              if (!compact && meta.isNotEmpty) ...[
                const SizedBox(width: 12),
                _MetaPill(meta),
              ],
            ],
          );
        },
      ),
    ),
  );
}

class _ServiceActionRow extends StatelessWidget {
  const _ServiceActionRow({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.meta,
    required this.actionLabel,
    required this.actionIcon,
    required this.onAction,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String meta;
  final String actionLabel;
  final IconData actionIcon;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: _HoverSurface(
      color: _Palette.of(context).surfaceRaised,
      padding: const EdgeInsets.all(15),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final stackActions = constraints.maxWidth < 640;
          final details = Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: _Palette.of(context).surfaceHover,
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Icon(icon, size: 19, color: _Palette.primary),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(fontWeight: FontWeight.w900),
                    ),
                    if (subtitle.isNotEmpty) ...[
                      const SizedBox(height: 5),
                      Text(
                        subtitle,
                        maxLines: 4,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: _Palette.of(context).muted,
                          fontSize: 12,
                          height: 1.5,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          );
          final actions = Wrap(
            spacing: 8,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              _MetaPill(meta),
              _ActionButton(
                label: actionLabel,
                icon: actionIcon,
                primary: onAction != null,
                onTap: onAction,
              ),
            ],
          );
          if (stackActions) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [details, const SizedBox(height: 12), actions],
            );
          }
          return Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(child: details),
              const SizedBox(width: 16),
              actions,
            ],
          );
        },
      ),
    ),
  );
}

class _CompactRow extends StatelessWidget {
  const _CompactRow({
    required this.leading,
    required this.title,
    this.subtitle = '',
  });
  final String leading;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 9),
    decoration: BoxDecoration(
      color: _Palette.of(context).surfaceRaised,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: _Palette.of(context).border),
    ),
    padding: const EdgeInsets.all(12),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          constraints: const BoxConstraints(minWidth: 32),
          height: 32,
          decoration: BoxDecoration(
            color: const Color(0x1FA7FF3C),
            borderRadius: BorderRadius.circular(9),
          ),
          alignment: Alignment.center,
          padding: const EdgeInsets.symmetric(horizontal: 7),
          child: Text(
            leading,
            style: const TextStyle(
              color: _Palette.primary,
              fontSize: 11,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                ),
              ),
              if (subtitle.isNotEmpty) ...[
                const SizedBox(height: 3),
                Text(
                  subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: _Palette.of(context).muted,
                    fontSize: 11,
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    ),
  );
}

class _ProgressRow extends StatelessWidget {
  const _ProgressRow({
    required this.label,
    required this.value,
    required this.trailing,
  });
  final String label;
  final double value;
  final String trailing;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: Column(
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Text(
              trailing,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900),
            ),
          ],
        ),
        const SizedBox(height: 7),
        _AnimatedProgress(value: value / 100),
      ],
    ),
  );
}

class _AnimatedProgress extends StatelessWidget {
  const _AnimatedProgress({required this.value});
  final double value;

  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
    tween: Tween(begin: 0, end: value.clamp(0, 1)),
    duration: const Duration(milliseconds: 680),
    curve: const Cubic(0.2, 0.8, 0.2, 1),
    builder: (context, current, _) => ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: LinearProgressIndicator(
        value: current,
        minHeight: 7,
        color: _Palette.primary,
        backgroundColor: _Palette.of(context).surfaceHover,
      ),
    ),
  );
}

class _SmallMetricRow extends StatelessWidget {
  const _SmallMetricRow({required this.values});
  final List<(String, String)> values;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final columns = constraints.maxWidth >= 840
          ? 4
          : constraints.maxWidth >= 420
          ? 2
          : 1;
      final spacing = 16.0 * (columns - 1);
      final width = (constraints.maxWidth - spacing) / columns;
      return Wrap(
        spacing: 16,
        runSpacing: 16,
        children: values.indexed
            .map(
              (entry) => SizedBox(
                width: width,
                child: _Reveal(
                  index: entry.$1,
                  child: _HoverSurface(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          entry.$2.$1,
                          style: TextStyle(
                            color: _Palette.of(context).muted,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          entry.$2.$2,
                          style: const TextStyle(
                            color: _Palette.primary,
                            fontSize: 28,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            )
            .toList(),
      );
    },
  );
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.title, required this.subtitle});
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Text(
        title,
        style: const TextStyle(
          color: _Palette.primary,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
      const SizedBox(width: 10),
      Expanded(
        child: Text(
          subtitle,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(color: _Palette.of(context).muted, fontSize: 12),
        ),
      ),
    ],
  );
}

class _SettingToggle extends StatelessWidget {
  const _SettingToggle({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });
  final IconData icon;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Material(
      color: _Palette.of(context).surfaceRaised,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: _Palette.of(context).border),
      ),
      clipBehavior: Clip.antiAlias,
      child: SwitchListTile(
        value: value,
        onChanged: onChanged,
        activeTrackColor: _Palette.primary,
        activeThumbColor: const Color(0xFF10150C),
        secondary: Icon(icon),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
        subtitle: Text(
          subtitle,
          style: TextStyle(color: _Palette.of(context).muted, fontSize: 12),
        ),
      ),
    ),
  );
}

class _KeyValue extends StatelessWidget {
  const _KeyValue(this.label, this.value);
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 150,
          child: Text(
            label,
            style: TextStyle(color: _Palette.of(context).muted),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ),
      ],
    ),
  );
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.label,
    required this.onTap,
    this.primary = false,
    this.danger = false,
    this.icon,
  });
  final String label;
  final VoidCallback? onTap;
  final bool primary;
  final bool danger;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final palette = _Palette.of(context);
    final color = danger
        ? _Palette.danger
        : primary
        ? _Palette.primary
        : palette.surfaceRaised;
    final foreground = primary ? const Color(0xFF10150C) : palette.text;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: AnimatedOpacity(
          duration: const Duration(milliseconds: 140),
          opacity: onTap == null ? 0.55 : 1,
          child: Container(
            constraints: const BoxConstraints(minHeight: 42),
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: danger
                    ? _Palette.danger
                    : primary
                    ? _Palette.primary
                    : palette.border,
              ),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 17, color: foreground),
                  const SizedBox(width: 8),
                ],
                Flexible(
                  child: Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: foreground,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _MiniButton extends StatelessWidget {
  const _MiniButton({required this.label, required this.onTap});
  final String label;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 34,
    child: _ActionButton(label: label, onTap: onTap),
  );
}

class _ShellButton extends StatelessWidget {
  const _ShellButton({
    required this.tooltip,
    required this.onTap,
    required this.child,
  });
  final String tooltip;
  final VoidCallback onTap;
  final Widget child;

  @override
  Widget build(BuildContext context) => Tooltip(
    message: tooltip,
    child: Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          width: double.infinity,
          height: 38,
          decoration: BoxDecoration(
            color: _Palette.of(context).surfaceRaised,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: _Palette.of(context).border),
          ),
          child: child,
        ),
      ),
    ),
  );
}

class _StatusDot extends StatelessWidget {
  const _StatusDot();
  @override
  Widget build(BuildContext context) => Container(
    width: 12,
    height: 12,
    margin: const EdgeInsets.only(top: 4),
    decoration: const BoxDecoration(
      color: _Palette.info,
      shape: BoxShape.circle,
      boxShadow: [BoxShadow(color: Color(0x3375D7FF), spreadRadius: 6)],
    ),
  );
}

class _MetaPill extends StatelessWidget {
  const _MetaPill(this.label);
  final String label;
  @override
  Widget build(BuildContext context) => Container(
    decoration: BoxDecoration(
      color: _Palette.of(context).surfaceHover,
      borderRadius: BorderRadius.circular(9),
    ),
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
    child: Text(
      label,
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: TextStyle(
        color: _Palette.of(context).muted,
        fontSize: 11,
        fontWeight: FontWeight.w800,
      ),
    ),
  );
}

class _SignalPill extends StatelessWidget {
  const _SignalPill(this.label, this.color);
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
    constraints: const BoxConstraints(maxWidth: 320),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.12),
      border: Border.all(color: color.withValues(alpha: 0.42)),
      borderRadius: BorderRadius.circular(9),
    ),
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            label,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: _Palette.of(context).text,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ],
    ),
  );
}

class _ActionMetricStrip extends StatelessWidget {
  const _ActionMetricStrip({required this.metrics});
  final List<
    ({String label, String value, String caption, IconData icon, Color color})
  >
  metrics;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final columns = constraints.maxWidth >= 760 ? 4 : 2;
      final width = (constraints.maxWidth - ((columns - 1) * 10)) / columns;
      return Wrap(
        spacing: 10,
        runSpacing: 10,
        children: metrics
            .map(
              (metric) => SizedBox(
                width: width,
                child: Container(
                  height: 88,
                  padding: const EdgeInsets.all(13),
                  decoration: BoxDecoration(
                    color: _Palette.of(context).surfaceRaised,
                    border: Border.all(color: _Palette.of(context).border),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(
                          color: metric.color.withValues(alpha: 0.14),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(metric.icon, color: metric.color, size: 19),
                      ),
                      const SizedBox(width: 11),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              metric.value,
                              style: const TextStyle(
                                fontSize: 23,
                                height: 1,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              metric.label,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            Text(
                              metric.caption,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: _Palette.of(context).muted,
                                fontSize: 10,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            )
            .toList(),
      );
    },
  );
}

class _ActionFilterButton extends StatelessWidget {
  const _ActionFilterButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
    color: selected ? _Palette.primary : _Palette.of(context).surfaceRaised,
    borderRadius: BorderRadius.circular(10),
    child: InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        height: 40,
        constraints: const BoxConstraints(minWidth: 76),
        alignment: Alignment.center,
        padding: const EdgeInsets.symmetric(horizontal: 14),
        decoration: BoxDecoration(
          border: Border.all(
            color: selected ? _Palette.primary : _Palette.of(context).border,
          ),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected
                ? const Color(0xFF10150C)
                : _Palette.of(context).text,
            fontSize: 12,
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
    ),
  );
}

class _WorkspaceSearch extends StatelessWidget {
  const _WorkspaceSearch({
    required this.controller,
    required this.hint,
    required this.onChanged,
  });
  final TextEditingController controller;
  final String hint;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) => TextField(
    controller: controller,
    onChanged: onChanged,
    decoration: InputDecoration(
      hintText: hint,
      prefixIcon: const Icon(Icons.search_rounded, size: 20),
      suffixIcon: controller.text.isEmpty
          ? null
          : IconButton(
              tooltip: 'Clear search',
              icon: const Icon(Icons.close_rounded, size: 18),
              onPressed: () {
                controller.clear();
                onChanged('');
              },
            ),
      filled: true,
      fillColor: _Palette.of(context).surfaceRaised,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: _Palette.of(context).border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: BorderSide(color: _Palette.of(context).border),
      ),
    ),
  );
}

Color _opportunityTone(Map<String, dynamic> item) =>
    switch (_string(item['urgency'])) {
      'overdue' => _Palette.danger,
      'urgent' => _Palette.warning,
      'action' => _Palette.info,
      _ when item['is_achievement'] == true => _Palette.success,
      _ => _Palette.primary,
    };

Color _deadlineTone(Map<String, dynamic> item) {
  final days = (item['days_left'] as num?)?.toInt();
  if (days == null) return _Palette.info;
  if (days < 0) return _Palette.danger;
  if (days <= 3) return _Palette.warning;
  return _Palette.info;
}

String _shortDeadline(Map<String, dynamic> item) {
  final days = (item['days_left'] as num?)?.toInt();
  if (days == null) return 'No deadline';
  if (days < 0) return '${days.abs()}d overdue';
  if (days == 0) return 'Due today';
  return '${days}d left';
}

IconData _opportunityIcon(Map<String, dynamic> item) {
  final status = _string(item['status']).toLowerCase();
  final kind = _string(item['kind']).toLowerCase();
  if (item['is_achievement'] == true) {
    return Icons.emoji_events_outlined;
  }
  if (status.contains('interview')) {
    return Icons.record_voice_over_outlined;
  }
  if (status.contains('assessment') || status.contains('round')) {
    return Icons.assignment_outlined;
  }
  if (kind.contains('hackathon') || kind.contains('competition')) {
    return Icons.code_rounded;
  }
  return Icons.work_outline;
}

Color _reminderTone(Map<String, dynamic> item) =>
    switch (_string(item['urgency'])) {
      'overdue' => _Palette.danger,
      'today' => _Palette.warning,
      _ => _Palette.info,
    };

IconData _reminderIcon(Map<String, dynamic> item) =>
    switch (_string(item['urgency'])) {
      'overdue' => Icons.priority_high_rounded,
      'today' => Icons.schedule_rounded,
      _ => Icons.notifications_none,
    };

class _Eyebrow extends StatelessWidget {
  const _Eyebrow(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Text(
      text,
      style: const TextStyle(
        color: _Palette.primary,
        fontSize: 12,
        fontWeight: FontWeight.w900,
      ),
    ),
  );
}

class _Empty extends StatelessWidget {
  const _Empty(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 22),
    child: Center(
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: TextStyle(color: _Palette.of(context).muted),
      ),
    ),
  );
}

class _Palette {
  const _Palette({
    required this.background,
    required this.sidebar,
    required this.surface,
    required this.surfaceRaised,
    required this.surfaceHover,
    required this.border,
    required this.borderStrong,
    required this.text,
    required this.muted,
  });

  static const primary = Color(0xFFA7FF3C);
  static const info = Color(0xFF75D7FF);
  static const success = Color(0xFF72E6A2);
  static const warning = Color(0xFFFFD166);
  static const danger = Color(0xFFFF7B86);
  static const mutedDark = Color(0xFFA7B0A4);

  final Color background;
  final Color sidebar;
  final Color surface;
  final Color surfaceRaised;
  final Color surfaceHover;
  final Color border;
  final Color borderStrong;
  final Color text;
  final Color muted;

  static _Palette of(BuildContext context) {
    if (Theme.of(context).brightness == Brightness.light) {
      return const _Palette(
        background: Color(0xFFF3F5F0),
        sidebar: Color(0xFFF8FAF6),
        surface: Color(0xFFFFFFFF),
        surfaceRaised: Color(0xFFF0F3ED),
        surfaceHover: Color(0xFFE6EBE2),
        border: Color(0xFFD8DFD3),
        borderStrong: Color(0xFFADB9A8),
        text: Color(0xFF171B16),
        muted: Color(0xFF667061),
      );
    }
    return const _Palette(
      background: Color(0xFF090B09),
      sidebar: Color(0xFF0D100D),
      surface: Color(0xFF121512),
      surfaceRaised: Color(0xFF181C18),
      surfaceHover: Color(0xFF1D221D),
      border: Color(0xFF293029),
      borderStrong: Color(0xFF3A4439),
      text: Color(0xFFF4F7F2),
      muted: Color(0xFFA7B0A4),
    );
  }
}

String _greeting() {
  final hour = DateTime.now().hour;
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

String _friendlyDate(dynamic value) {
  final text = _string(value);
  if (text.isEmpty) return 'No date stated';
  final parsed = DateTime.tryParse(text);
  if (parsed == null) return text;
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  final hour = parsed.hour == 0
      ? 12
      : parsed.hour > 12
      ? parsed.hour - 12
      : parsed.hour;
  final minute = parsed.minute.toString().padLeft(2, '0');
  final suffix = parsed.hour >= 12 ? 'PM' : 'AM';
  return '${parsed.day} ${months[parsed.month - 1]} $hour:$minute $suffix';
}

String _string(dynamic value, {String fallback = ''}) {
  final text = value?.toString().trim() ?? '';
  if (text.isEmpty || text == 'null') return fallback;
  return text
      .replaceAll('&amp;', '&')
      .replaceAll('&lt;', '<')
      .replaceAll('&gt;', '>')
      .replaceAll('Â·', '-')
      .replaceAll('âœ“', 'Done');
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
