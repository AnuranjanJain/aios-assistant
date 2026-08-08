# AiOS Refactoring Roadmap

Audit date: 2026-08-08

## Done in this hardening pass

1. One-time native/browser pairing and authenticated agent APIs.
2. Loopback-only local AI egress and untrusted-email prompt boundaries.
3. Duplicate Gmail scheduler ownership, retry/checkpoint behavior, and notification claims.
4. SQLite FK/WAL settings, pre-migration backups, atomic runtime state, and bounded inputs.
5. Browser redirect checks, symlink rejection, profile-image sanitization, extension destination checks.
6. Clean dependency audits, configurable Windows build paths, external OAuth, manifest/SHA/SBOM hooks.
7. Deterministic AI quality smoke tests and regression coverage.

## Next release phase

1. Install Flutter and run analyzer, widget, Windows package, installer, upgrade, uninstall, and high-DPI checks.
2. Add Authenticode signing and fail public-release builds with `-RequireSigning` when no certificate is present.
3. [x] Move the native token to Windows Credential Manager; retain OS-level verification as a release checklist item.
4. Replace handwritten migrations with a versioned migration/rollback system.
5. Add data inventory, retention, export, and purge controls.
6. Add critical-module coverage thresholds, clean subprocess repetition, live Gmail fixtures, and browser/GitHub integration fixtures.
7. Add a redacted AI corpus with calibration and abstention metrics.

## Architecture direction

```text
Native client / WDYD companion
            |
      Authenticated local core
            |
    Durable jobs and source cursors
      /       |        |       \
   Gmail   Memory   Planner   Agents
            |
      Versioned local stores
```

The activity collector remains a deliberate WDYD companion responsibility. AiOS consumes a minimized snapshot through an authenticated boundary instead of collecting private desktop signals twice.
