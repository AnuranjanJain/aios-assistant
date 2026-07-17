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
    (id: 'projects', label: 'Projects', icon: Icons.account_tree_outlined),
    (id: 'wellbeing', label: 'Wellbeing', icon: Icons.favorite_border),
    (id: 'memory', label: 'Memory', icon: Icons.storage_outlined),
    (id: 'planner', label: 'Planner', icon: Icons.calendar_today_outlined),
    (
      id: 'command-planner',
      label: 'Command Planner',
      icon: Icons.event_note_outlined,
    ),
    (id: 'automation', label: 'Automation', icon: Icons.terminal_rounded),
    (id: 'browser-agent', label: 'Browser Agent', icon: Icons.public),
    (id: 'career', label: 'Career Copilot', icon: Icons.school_outlined),
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
    return Scaffold(
      backgroundColor: _Palette.of(context).background,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              _Sidebar(
                controller: widget.controller,
                scrollController: _sidebarScroll,
                compact: compactSidebar,
              ),
              const SizedBox(width: 20),
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
          color: _Palette.primary,
          shape: BoxShape.circle,
          boxShadow: const [
            BoxShadow(color: Color(0x1FA7FF3C), spreadRadius: 7, blurRadius: 2),
          ],
        ),
        alignment: Alignment.center,
        child: const Text(
          'A',
          style: TextStyle(
            color: Color(0xFF10150C),
            fontSize: 20,
            fontWeight: FontWeight.w900,
          ),
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
                      'Your Schedule',
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
      (id: 'opportunities', label: 'Hackathons', icon: Icons.work_outline),
      (id: 'command-planner', label: 'Plan', icon: Icons.event_note_outlined),
      (id: 'career', label: 'Jobs', icon: Icons.school_outlined),
      (id: 'wellbeing', label: 'Wellbeing', icon: Icons.favorite_border),
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
          final active =
              controller.activePage == entry.id ||
              (entry.id == 'sources' && controller.activePage == 'inbox');
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
      'projects' => _ProjectsPage(controller: controller),
      'wellbeing' => _WellbeingPage(controller: controller),
      'memory' => _MemoryPage(controller: controller),
      'planner' => _PlannerPage(controller: controller),
      'command-planner' => _CommandPlannerPage(controller: controller),
      'automation' => _AutomationPage(controller: controller),
      'browser-agent' => _BrowserAgentPage(controller: controller),
      'career' => _CareerPage(controller: controller),
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
    final plan = _map(controller.live['plan']);
    final opportunities = [
      ..._maps(controller.live['achievements']),
      ..._maps(controller.live['opportunities']),
    ];
    final reminders = _maps(controller.live['reminders']);
    final activities = _maps(controller.live['activities']);
    final summary = _string(
      plan['summary'],
      fallback: 'Your local assistant is building today\'s plan.',
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Reveal(
          index: 0,
          child: _Hero(controller: controller, summary: summary),
        ),
        const SizedBox(height: 12),
        _MetricGrid(stats: stats),
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
              latestActivity: activities.isEmpty ? const {} : activities.first,
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
  const _MetricGrid({required this.stats});
  final Map<String, dynamic> stats;

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
          'AI Confidence',
          '${stats['avg_confidence'] ?? 0}%',
          'recent inbox average',
        ),
        ('Wellbeing', '${stats['wellbeing_minutes'] ?? 0}', 'minutes observed'),
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
  const _AgentSummary({required this.summary, required this.latestActivity});
  final String summary;
  final Map<String, dynamic> latestActivity;

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
            'Today at a glance',
            style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 12),
          _SummaryCard(label: 'Focus plan', value: summary),
          const SizedBox(height: 10),
          _SummaryCard(
            label: 'Latest signal',
            value: _string(
              latestActivity['agent_summary'],
              fallback: 'Connect What Do You Do for live context.',
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
    final plan = _map(controller.live['plan']);
    final blocks = _strings(plan['focus_blocks']);
    final graph = _maps(_map(controller.live['stats'])['opportunity_graph']);
    final activities = _maps(controller.live['activities']);
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
                eyebrow: 'TODAY',
                title: 'Focus Plan',
                child: blocks.isEmpty
                    ? const _Empty('No focus blocks yet.')
                    : Column(
                        children: blocks
                            .take(5)
                            .toList()
                            .indexed
                            .map(
                              (entry) => _CompactRow(
                                leading: '${entry.$1 + 1}',
                                title: entry.$2,
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
                eyebrow: 'WHAT DO YOU DO',
                title: 'Activity Feed',
                child: activities.isEmpty
                    ? const _Empty('Activity signals will appear here.')
                    : Column(
                        children: activities
                            .take(5)
                            .map(
                              (item) => _CompactRow(
                                leading: '${item['duration_minutes'] ?? 0}m',
                                title: _string(
                                  item['app_name'],
                                  fallback: _string(item['category']),
                                ),
                                subtitle: _string(item['agent_summary']),
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

class _OpportunitiesPage extends StatelessWidget {
  const _OpportunitiesPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final achievements = _maps(controller.live['achievements']);
    final deadlines = _maps(controller.live['deadline_highlights']);
    final opportunities = _maps(controller.live['opportunities']);
    return _PageColumn(
      children: [
        _Panel(
          eyebrow: 'PIPELINE',
          title: 'Tracked Opportunities',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (achievements.isNotEmpty) ...[
                const _SectionLabel(
                  title: 'Achievements',
                  subtitle: 'Selections and milestones detected from Gmail',
                ),
                const SizedBox(height: 10),
                ...achievements.map((item) => _AchievementCard(item: item)),
                const SizedBox(height: 18),
              ],
              if (deadlines.isNotEmpty) ...[
                const _SectionLabel(
                  title: 'Build timeline',
                  subtitle: 'Submission windows detected from recent mail',
                ),
                const SizedBox(height: 10),
                ...deadlines.map((item) => _DeadlineCard(item: item)),
                const SizedBox(height: 18),
              ],
              if (opportunities.isEmpty)
                const _Empty('No tracked opportunity.')
              else
                ...opportunities.indexed.map(
                  (entry) => _Reveal(
                    index: entry.$1,
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: _OpportunityRow(item: entry.$2),
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

class _AchievementCard extends StatelessWidget {
  const _AchievementCard({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: _HoverSurface(
      color: _Palette.of(context).surfaceRaised,
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: const BoxDecoration(
              color: Color(0x2672E6A2),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.check_rounded, color: _Palette.success),
          ),
          const SizedBox(width: 13),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _string(item['status'], fallback: 'Achievement'),
                  style: const TextStyle(
                    color: _Palette.primary,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  _string(item['title']),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class _DeadlineCard extends StatelessWidget {
  const _DeadlineCard({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final days = item['days_left'];
    final urgent = days is num && days <= 3;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: _HoverSurface(
        color: _Palette.of(context).surfaceRaised,
        borderColor: urgent ? _Palette.warning : null,
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: urgent
                    ? const Color(0x24FFD166)
                    : const Color(0x1FA7FF3C),
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: Text(
                days?.toString() ?? '?',
                style: TextStyle(
                  color: urgent ? _Palette.warning : _Palette.primary,
                  fontSize: 20,
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
                      item['deadline_message'],
                      fallback: 'Upcoming deadline',
                    ),
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _string(item['title']),
                    maxLines: 2,
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
        ),
      ),
    );
  }
}

class _OpportunityRow extends StatelessWidget {
  const _OpportunityRow({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) => _HoverSurface(
    color: _Palette.of(context).surfaceRaised,
    padding: const EdgeInsets.all(16),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const _StatusDot(),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _string(item['title'], fallback: 'Opportunity'),
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 6),
              Text(
                '${_string(item['kind'])} - ${_string(item['status'])} - ${_string(item['organization'])}',
                style: TextStyle(
                  color: _Palette.of(context).muted,
                  fontSize: 12,
                ),
              ),
              if (_string(item['deadline_message']).isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  _string(item['deadline_message']),
                  style: const TextStyle(
                    color: _Palette.warning,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              if (_string(item['notes']).isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  _string(item['notes']),
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(height: 1.5),
                ),
              ],
            ],
          ),
        ),
      ],
    ),
  );
}

class _RemindersPage extends StatelessWidget {
  const _RemindersPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final reminders = _maps(controller.live['reminders']);
    return _PageColumn(
      children: [
        _Panel(
          eyebrow: 'LATEST 100 EMAILS',
          title: 'Today\'s tasks',
          child: reminders.isEmpty
              ? const _Empty('No email tasks are due today.')
              : Column(
                  children: reminders.indexed
                      .map(
                        (entry) => _Reveal(
                          index: entry.$1,
                          child: Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: _ListRow(
                              icon: Icons.notifications_none,
                              title: _string(
                                entry.$2['title'],
                                fallback: 'Reminder',
                              ),
                              subtitle: _friendlyDate(entry.$2['due_at']),
                              meta: _string(entry.$2['priority']),
                            ),
                          ),
                        ),
                      )
                      .toList(),
                ),
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
    return _PageColumn(
      children: [
        _Panel(
          eyebrow: 'CLASSIFIER',
          title: 'Recent Inbox Intelligence',
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

class _ProjectsPage extends StatelessWidget {
  const _ProjectsPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final projects = _maps(controller.projects['projects']);
    return _WorkspacePage(
      eyebrow: 'CONNECTED WORK',
      title: 'Projects',
      subtitle:
          'Repositories, local workspaces, milestones, and next actions in one view.',
      child: projects.isEmpty
          ? const _Panel(
              title: 'Project context',
              child: _Empty('No project context yet.'),
            )
          : Column(
              children: projects.indexed
                  .map(
                    (entry) => _Reveal(
                      index: entry.$1,
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 14),
                        child: _ProjectCard(item: entry.$2),
                      ),
                    ),
                  )
                  .toList(),
            ),
    );
  }
}

class _ProjectCard extends StatelessWidget {
  const _ProjectCard({required this.item});
  final Map<String, dynamic> item;

  @override
  Widget build(BuildContext context) {
    final progress = (item['progress'] as num?)?.toDouble() ?? 0;
    return _Panel(
      eyebrow: _string(
        item['status'],
        fallback: 'ACTIVE PROJECT',
      ).toUpperCase(),
      title: _string(item['title'], fallback: 'Project'),
      action: Text(
        '${progress.round()}%',
        style: const TextStyle(
          color: _Palette.primary,
          fontSize: 18,
          fontWeight: FontWeight.w900,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _AnimatedProgress(value: progress / 100),
          const SizedBox(height: 14),
          Text(
            _string(item['next_action'], fallback: 'Choose the next action.'),
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
          if (_string(item['repository']).isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              _string(item['repository']),
              style: TextStyle(color: _Palette.of(context).muted),
            ),
          ],
          if (_string(item['working_directory']).isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              _string(item['working_directory']),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: _Palette.of(context).muted, fontSize: 12),
            ),
          ],
        ],
      ),
    );
  }
}

class _WellbeingPage extends StatelessWidget {
  const _WellbeingPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final stats = _map(controller.live['stats']);
    final graph = _maps(stats['wellbeing_graph']);
    final activities = _maps(controller.live['activities']);
    return _WorkspacePage(
      eyebrow: 'LOCAL WELLBEING',
      title: 'Wellbeing',
      subtitle:
          'Private activity signals from What Do You Do, summarized on this device.',
      child: Column(
        children: [
          _Panel(
            eyebrow: 'TODAY',
            title: '${stats['wellbeing_minutes'] ?? 0} minutes observed',
            child: graph.isEmpty
                ? const _Empty(
                    'Wellbeing signals appear after local activity is observed.',
                  )
                : Column(
                    children: graph
                        .map(
                          (item) => _ProgressRow(
                            label: _string(item['label']),
                            value: (item['percent'] as num?)?.toDouble() ?? 0,
                            trailing: '${item['minutes'] ?? 0}m',
                          ),
                        )
                        .toList(),
                  ),
          ),
          const SizedBox(height: 16),
          _Panel(
            eyebrow: 'RECENT SIGNALS',
            title: 'Activity context',
            child: activities.isEmpty
                ? const _Empty('No activity context yet.')
                : Column(
                    children: activities
                        .map(
                          (item) => _ListRow(
                            icon: Icons.bolt_outlined,
                            title: _string(
                              item['app_name'],
                              fallback: _string(item['category']),
                            ),
                            subtitle: _string(item['agent_summary']),
                            meta: '${item['duration_minutes'] ?? 0}m',
                          ),
                        )
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _MemoryPage extends StatelessWidget {
  const _MemoryPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final data = controller.dataFor('memory');
    final counts = _map(data['counts']);
    final entities = _maps(data['entities']);
    return _WorkspacePage(
      eyebrow: 'PERSISTENT CONTEXT',
      title: 'Memory',
      subtitle:
          'Entities, relationships, and checkpoints retained locally across sessions.',
      child: Column(
        children: [
          _SmallMetricRow(
            values: [
              ('Entities', '${counts['entities'] ?? 0}'),
              ('Facts', '${counts['facts'] ?? 0}'),
              ('Projects', '${counts['projects'] ?? 0}'),
              ('Relations', '${counts['relations'] ?? 0}'),
            ],
          ),
          const SizedBox(height: 16),
          _Panel(
            eyebrow: 'KNOWLEDGE GRAPH',
            title: 'Remembered entities',
            child: entities.isEmpty
                ? const _Empty('No memory entities yet.')
                : Column(
                    children: entities
                        .map(
                          (item) => _ListRow(
                            icon: Icons.hub_outlined,
                            title: _string(item['name'], fallback: 'Entity'),
                            subtitle: _string(item['summary']),
                            meta: _string(item['entity_type']),
                          ),
                        )
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _PlannerPage extends StatelessWidget {
  const _PlannerPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final data = controller.dataFor('planner');
    final counts = _map(data['counts']);
    final plans = _maps(data['plans']);
    return _WorkspacePage(
      eyebrow: 'GOAL PLANNING',
      title: 'Planner',
      subtitle:
          'Turn goals into focused tasks and keep progress visible without losing history.',
      child: Column(
        children: [
          _SmallMetricRow(
            values: [
              ('Plans', '${counts['plans'] ?? 0}'),
              ('Active tasks', '${counts['active_tasks'] ?? 0}'),
              ('Completed', '${counts['completed_tasks'] ?? 0}'),
              ('Minutes', '${counts['minutes'] ?? 0}'),
            ],
          ),
          const SizedBox(height: 16),
          _Panel(
            eyebrow: 'ACTIVE PLANS',
            title: 'Goal workspace',
            child: plans.isEmpty
                ? const _Empty('No goal plan has been created yet.')
                : Column(
                    children: plans
                        .map(
                          (item) => _ListRow(
                            icon: Icons.flag_outlined,
                            title: _string(item['title'], fallback: 'Plan'),
                            subtitle: _string(item['summary']),
                            meta: _string(item['status']),
                          ),
                        )
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _CommandPlannerPage extends StatelessWidget {
  const _CommandPlannerPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final data = controller.dataFor('command-planner');
    final agenda = _map(data['agenda']);
    final items = [
      ..._maps(agenda['today']),
      ..._maps(agenda['week']),
      ..._maps(agenda['month']),
    ];
    final unique = <dynamic, Map<String, dynamic>>{};
    for (final item in items) {
      unique[item['id'] ?? item['title']] = item;
    }
    return _WorkspacePage(
      eyebrow: 'DAILY AI ASSISTANT',
      title: 'Command Planner',
      subtitle:
          'Deadlines, risks, and next actions selected from your connected life graph.',
      child: _Panel(
        eyebrow: 'AGENDA',
        title: 'Upcoming work',
        child: unique.isEmpty
            ? const _Empty('No planning events yet.')
            : Column(
                children: unique.values
                    .take(24)
                    .map(
                      (item) => _ListRow(
                        icon: Icons.event_note_outlined,
                        title: _string(
                          item['title'],
                          fallback: 'Planning event',
                        ),
                        subtitle: _string(
                          item['next_question'],
                          fallback: _string(item['work_left']),
                        ),
                        meta: _friendlyDate(item['deadline']),
                      ),
                    )
                    .toList(),
              ),
      ),
    );
  }
}

class _AutomationPage extends StatelessWidget {
  const _AutomationPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final data = controller.dataFor('automation');
    final counts = _map(data['counts']);
    final capabilities = _map(data['capabilities']);
    final plans = _maps(data['plans']);
    return _WorkspacePage(
      eyebrow: 'LOCAL ACTIONS',
      title: 'Automation',
      subtitle:
          'Audited file and workspace actions that stay inside approved local roots.',
      child: Column(
        children: [
          _SmallMetricRow(
            values: [
              ('Plans', '${counts['plans'] ?? 0}'),
              ('Actions', '${counts['actions'] ?? 0}'),
              ('Completed', '${counts['completed'] ?? 0}'),
              ('Failed', '${counts['failed'] ?? 0}'),
            ],
          ),
          const SizedBox(height: 16),
          _Panel(
            eyebrow: 'CAPABILITIES',
            title: 'Local execution boundary',
            child: Column(
              children: [
                _KeyValue(
                  'Local only',
                  '${capabilities['local_only'] == true}',
                ),
                _KeyValue(
                  'Desktop control',
                  '${capabilities['desktop_control_enabled'] == true}',
                ),
                _KeyValue(
                  'Audit database',
                  _string(capabilities['audit_database']),
                ),
                if (plans.isEmpty)
                  const _Empty('No automation plan is queued.'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _BrowserAgentPage extends StatelessWidget {
  const _BrowserAgentPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final data = controller.dataFor('browser-agent');
    final counts = _map(data['counts']);
    final capabilities = _map(data['capabilities']);
    final opportunities = _maps(data['opportunities']);
    return _WorkspacePage(
      eyebrow: 'ASSISTED BROWSING',
      title: 'Browser Agent',
      subtitle:
          'Prepare browsing work locally while keeping final submissions under your control.',
      child: Column(
        children: [
          _SmallMetricRow(
            values: [
              ('Plans', '${counts['plans'] ?? 0}'),
              ('Opportunities', '${counts['opportunities'] ?? 0}'),
              ('High match', '${counts['high_match'] ?? 0}'),
              ('Awaiting', '${counts['awaiting'] ?? 0}'),
            ],
          ),
          const SizedBox(height: 16),
          _Panel(
            eyebrow: 'CONTROL',
            title: 'Browser boundary',
            child: Column(
              children: [
                _KeyValue(
                  'Playwright',
                  '${capabilities['playwright_installed'] == true}',
                ),
                _KeyValue(
                  'Submission enabled',
                  '${capabilities['submission_enabled'] == true}',
                ),
                if (opportunities.isEmpty)
                  const _Empty('No browser opportunity is queued.'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CareerPage extends StatelessWidget {
  const _CareerPage({required this.controller});
  final AiosController controller;

  @override
  Widget build(BuildContext context) {
    final data = controller.dataFor('career');
    final counts = _map(data['counts']);
    final applications = _maps(data['applications']);
    final projects = _maps(data['projects']);
    return _WorkspacePage(
      eyebrow: 'CAREER GRAPH',
      title: 'Career Copilot',
      subtitle:
          'Applications, projects, skills, and evidence connected in one local career view.',
      child: Column(
        children: [
          _SmallMetricRow(
            values: [
              ('Applications', '${counts['applications'] ?? 0}'),
              ('Projects', '${counts['projects'] ?? 0}'),
              ('Repositories', '${counts['repositories'] ?? 0}'),
              ('Strong matches', '${counts['strong_matches'] ?? 0}'),
            ],
          ),
          const SizedBox(height: 16),
          _Panel(
            eyebrow: 'PIPELINE',
            title: 'Career evidence',
            child: applications.isEmpty && projects.isEmpty
                ? const _Empty(
                    'Career evidence will appear after sources are connected.',
                  )
                : Column(
                    children: [...applications, ...projects]
                        .take(15)
                        .map(
                          (item) => _ListRow(
                            icon: Icons.school_outlined,
                            title: _string(
                              item['title'],
                              fallback: _string(
                                item['name'],
                                fallback: 'Career item',
                              ),
                            ),
                            subtitle: _string(
                              item['summary'],
                              fallback: _string(item['description']),
                            ),
                            meta: _string(item['status']),
                          ),
                        )
                        .toList(),
                  ),
          ),
        ],
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
          const SizedBox(height: 16),
          _Panel(
            eyebrow: 'COLLEGE SIGNAL',
            title: _string(
              controller.college['headline'],
              fallback: 'PAT schedule',
            ),
            child: Text(
              _string(
                controller.college['latest_summary'],
                fallback: 'No recent PAT mail was detected.',
              ),
              style: const TextStyle(height: 1.55),
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
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _ActionButton(
                label: 'Continue in browser',
                primary: true,
                onTap: controller.continueGoogleSignIn,
              ),
              const SizedBox(width: 10),
              _ActionButton(
                label: 'Cancel sign in',
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
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: _HoverSurface(
        color: _Palette.of(context).surfaceRaised,
        padding: const EdgeInsets.all(15),
        child: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: const BoxDecoration(
                color: Color(0x1FA7FF3C),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: const Icon(Icons.mail_outline, color: _Palette.primary),
            ),
            const SizedBox(width: 13),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _string(
                      item['email'],
                      fallback: _string(
                        item['label'],
                        fallback: 'Google account',
                      ),
                    ),
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
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
            IconButton(
              tooltip: 'Sync account',
              onPressed: id == null || controller.syncing
                  ? null
                  : () => controller.syncAccount(id),
              icon: const Icon(Icons.sync),
            ),
            IconButton(
              tooltip: 'Disconnect account',
              onPressed: id == null ? null : () => controller.removeAccount(id),
              icon: const Icon(Icons.link_off_outlined),
            ),
          ],
        ),
      ),
    );
  }
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
                      (item) => _ListRow(
                        icon: item['configured'] == true
                            ? Icons.check_circle_outline
                            : Icons.info_outline,
                        title: _string(item['name'], fallback: 'Connector'),
                        subtitle: _string(item['description']),
                        meta: item['configured'] == true
                            ? 'Configured'
                            : 'Needs setup',
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
                return _ListRow(
                  icon: item['running'] == true
                      ? Icons.play_circle_outline
                      : Icons.pause_circle_outline,
                  title: _string(item['name'], fallback: 'Worker'),
                  subtitle: _string(item['description']),
                  meta: item['running'] == true ? 'Running' : 'Stopped',
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
                  onChanged: (value) => controller.setStartup(enabled: value),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: _ActionButton(
                        label: 'Hide to tray',
                        onTap: controller.hideToTray,
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _ActionButton(
                        label: 'Exit AiOS',
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
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(2, 10, 2, 20),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Eyebrow(eyebrow),
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 40,
                      height: 1.1,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    subtitle,
                    style: TextStyle(
                      color: _Palette.of(context).muted,
                      height: 1.5,
                    ),
                  ),
                ],
              ),
            ),
            if (actions.isNotEmpty) ...[
              const SizedBox(width: 18),
              Wrap(spacing: 10, runSpacing: 10, children: actions),
            ],
          ],
        ),
      ),
      child,
    ],
  );
}

class _PageColumn extends StatelessWidget {
  const _PageColumn({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topLeft,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 760),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    ),
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
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
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
              ),
            ),
            if (action != null) ...[const SizedBox(width: 12), action!],
          ],
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
      child: Row(
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
          if (meta.isNotEmpty) ...[const SizedBox(width: 12), _MetaPill(meta)],
        ],
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
      final width = (constraints.maxWidth - 48) / 4;
      return Wrap(
        spacing: 16,
        runSpacing: 16,
        children: values.indexed
            .map(
              (entry) => SizedBox(
                width: width.clamp(150, constraints.maxWidth),
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
  Widget build(BuildContext context) => Container(
    margin: const EdgeInsets.only(bottom: 10),
    decoration: BoxDecoration(
      color: _Palette.of(context).surfaceRaised,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: _Palette.of(context).border),
    ),
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
  });
  final String label;
  final VoidCallback? onTap;
  final bool primary;
  final bool danger;

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
            alignment: Alignment.center,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(
              label,
              style: TextStyle(color: foreground, fontWeight: FontWeight.w900),
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
