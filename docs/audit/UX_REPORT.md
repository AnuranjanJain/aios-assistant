# AiOS UX Report

Audit date: 2026-08-08

## What is working

The Flutter shell has one shared navigation frame, icon-based navigation, page transitions, saved local snapshots, startup/background controls, and focused widget tests. Flask fallback pages expose loading, empty, error, and reduced-motion states. Dynamic list renderers escape user/source content.

## Evidence gap

Flutter 3.44.2 is installed. Analyzer, 10 widget tests including high-DPI layout, compact-layout checks, a clean Windows package, packaged-core smoke, and isolated installer upgrade/uninstall pass. Keyboard navigation, screen-reader behavior, forced-colors behavior, and manual desktop verification remain.

## Remaining UX work

- Use one operation status model for OAuth, Gmail sync, browser plans, and workers: progress, checkpoint, retry, cancel, and last success.
- Add a data inventory with export, retention, and purge controls.
- Distinguish WDYD activity states: not connected, paused, permission denied, stale, and live.
- Label partial coverage for generic job-site selectors, GitHub depth, and connector imports.
- Verify 100%, 125%, 150%, and 200% Windows scaling, keyboard order, visible focus, and reduced motion on the packaged app.

## Acceptance criteria

Every page should have loading, empty, stale, error, offline, permission, and retry states. No dynamic text may clip or overlap at supported scaling. A signed Windows smoke build must be used for final visual verification.
