# Changelog

All notable changes to AiOS Assistant are documented here.

This project follows a practical release-candidate workflow. A version is only
called released after the native Windows bundle, installer lifecycle, signing,
and live connector checks have passed.

## [Unreleased] - 2026-08-08

### Added

- Local privacy center with a data inventory, secret-redacted export, retention
  controls, and scoped purge actions for email, activity, opportunities,
  memory, or all local data.
- Native Flutter privacy panel with category visibility, retention settings,
  export, and confirmation-gated deletion.
- Automatic operational-history retention during background email scans.
- Optional Windows startup launcher through the native installer with hidden
  background startup support.
- Graceful native shutdown before installer upgrade or uninstall, with a
  bounded forced-cleanup fallback for recovery.
- Release verification script for manifest provenance, payload hashes, file
  sizes, required files, credential-like filenames, and Authenticode status.
- Windows privacy-check script for local ownership and broad-write ACL checks.
- First-run readiness panel with essential versus optional setup checks and
  direct navigation to Gmail, worker, Settings, and Memory setup.
- Native core contract handshake that rejects stale local backends instead of
  silently pairing a newer client with an older installed core.

### Changed

- Windows native builds now fail closed when dependency installation,
  PyInstaller, Flutter, or SBOM generation fails.
- Release manifests now record the source commit and whether the source tree
  was dirty at build time.
- Desktop build output remains isolated from the existing installed app when a
  native build cannot complete.
- Performance smoke tests now accept dataset size, sample count, and p95
  limits from the command line.
- Audit and installation documentation now describe the current native
  release-candidate state, privacy controls, startup services, and external
  release gates.

### Fixed

- Privacy exports now redact OAuth tokens, API keys, bot tokens, bearer
  credentials, client secrets, authorization URLs, and sensitive setting
  values.
- SQLAlchemy OAuth table names used by privacy purge and export paths now match
  the actual model metadata.
- Background retention and installer shutdown paths are covered by regression
  tests.
- Native installer smoke coverage now checks startup launcher creation,
  upgrade behavior, and uninstall cleanup.
- A running background worker with a failed last cycle is now surfaced as an
  attention state instead of being reported as healthy.

### Verification

- Python suite: **124 passed, 1 skipped**.
- Native Flutter suite: **10 passed**; `flutter analyze` reports no issues.
- Dependency audits: `pip-audit` reports no known vulnerabilities for the
  audited requirement sets.
- AI quality gate: 16 redacted synthetic cases passed with macro F1 1.00,
  actionable F1 1.00, ECE 0.1869, and prompt-injection safety.
- Synthetic 100,000-message benchmark passed with `/api/live` p95 265.51 ms
  and `/api/inbox/overview` p95 50.10 ms.
- Current source privacy ACL check passed for the managed local directories.

### Release notes

- This commit is a **local release-candidate source snapshot**, not a signed
  public Windows release.
- A fresh plugin-enabled Flutter Windows build is still blocked on this
  machine because Windows Developer Mode is disabled.
- Existing binaries remain unsigned and the current historical manifest lacks
  source provenance; the release verifier correctly rejects it for public
  release use.
- Live Gmail, job-platform, and wellbeing-account fixtures, clean-account
  Credential Manager verification, Authenticode signing, and manual native
  accessibility checks remain before a public release.

## [0.3.0]

- Initial native Flutter desktop direction and local AiOS companion workflow.

[Unreleased]: https://github.com/AnuranjanJain/aios-assistant/compare/windows-native...HEAD
[0.3.0]: https://github.com/AnuranjanJain/aios-assistant/releases/tag/v0.3.0
