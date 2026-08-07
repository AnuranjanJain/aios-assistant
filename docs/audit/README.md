# AiOS Production Readiness Audit

Audit date: 2026-08-08

## Current verdict

**Evidence score: 89/100.** The critical local-security, duplicate-worker, migration, bounded-work, and deterministic AI-gate findings are addressed in this worktree. AiOS is a verified local release candidate: the Windows artifact builds, pairs, serves authenticated data, survives an isolated install/upgrade/uninstall cycle, and has synthetic 10k-message p95 evidence. It is not an honest 100/100 public release until signing, live connector fixtures, OS privacy verification, and manual accessibility review exist.

## Evidence snapshot

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 116 passed, 1 platform-dependent symlink test skipped |
| `python -m coverage run --branch -m pytest -q` | 116 passed; 73% combined coverage |
| `python -m compileall -q ...` | Passed |
| `python -m pip_audit -r requirements.txt` | No known vulnerabilities |
| `python -m pip_audit -r requirements-memory.txt` | No known vulnerabilities |
| `scripts/ai_quality_gate.py` | Passed: 16 redacted synthetic cases; macro F1 1.00, actionable F1 1.00, ECE 0.1869, abstention 0.125 |
| `scripts/performance_smoke.py` | Passed: synthetic 10,000-message SQLite set; `/api/live` p95 213.67 ms, inbox p95 23.83 ms |
| Versioned migration/rollback test | Passed: named ledger, checksum validation, consistent backup, explicit restore, idempotent rerun |
| PowerShell build-script parse | Passed |
| Flutter analyzer | Passed: Flutter 3.44.2 |
| Flutter widget tests | Passed: 10 tests, including high-DPI layout |
| Windows native build | Passed: Python 3.13.14 + Flutter 3.44.2 |
| Packaged core pairing/live smoke | Passed: authenticated `/api/live`, no leftover process/port/temp data |
| Isolated installer lifecycle smoke | Passed: full UI/core payload copied to `%TEMP%`, exact uninstaller removed it |
| Release metadata | Passed: 18-file manifest, SHA-256 checksums, CycloneDX SBOM, explicit unsigned marker |
| Gmail/GitHub/browser live E2E | Not run: no external test credentials or fixtures used |

## What changed

- Native pairing is now one-time, challenge-approved, or process-secret based; the runtime descriptor contains metadata only.
- Local Ollama URLs are validated before save and before every request.
- Standalone automation, browser, and career APIs require the local token.
- CORS/origin checks no longer treat a localhost port as browser identity, and LAN binding requires explicit opt-in plus a token.
- SQLite foreign keys, WAL, busy timeout, migration backups, notification claims, atomic state writes, and Gmail retry/deletion handling are in place.
- SQLite migrations now use named, checksummed steps with one consistent backup per upgrade and an explicit offline rollback command. The startup path refuses a changed checksum and never silently replaces a live database.
- Imports, analytics, profile images, browser redirects, extension destinations, and agent request bodies are bounded.
- The deterministic triage gate measures category precision/recall/F1, actionable F1, calibration error, abstention, and prompt-injection handling against a redacted synthetic corpus.
- A repeatable synthetic performance smoke measures warm dashboard reads against 10,000 stored messages.
- OAuth JSON stays external in `%APPDATA%\AiOS Assistant\credentials`; it is never embedded in a release executable.
- The Windows build produces a manifest, SHA-256 file, CycloneDX SBOM when `pip-audit` is installed, and an explicit unsigned-build marker.
- The native bearer token is stored in Windows secure storage; JSON preferences retain only non-secret UI/API metadata. Legacy JSON tokens migrate on the next successful start.

## Remaining release gates

1. Run native startup, high-DPI, keyboard, screen-reader, forced-colors, and reduced-motion checks on a real Windows desktop; isolated install/upgrade/uninstall smoke already passes.
2. Configure Authenticode signing and run `scripts/build-windows-native.ps1 -RequireSigning`.
3. Add OS ACL verification and user-facing retention/export/purge controls.
4. Replace the synthetic AI fixture with consented redacted labels and compare drift over time.
5. Run live Gmail multi-account, OAuth-expiry, GitHub-rate-limit, and browser redirect fixtures.

The desktop activity collector remains owned by the What Do You Do companion boundary. AiOS consumes its privacy-minimized activity snapshot; it does not silently duplicate keystroke/window surveillance.

## Reports

- [Engineering Audit](ENGINEERING_AUDIT.md)
- [Technical Debt](TECHNICAL_DEBT.md)
- [Security](SECURITY_REPORT.md)
- [Performance](PERFORMANCE_REPORT.md)
- [AI Quality](AI_QUALITY_REPORT.md)
- [UX](UX_REPORT.md)
- [Production Readiness](PRODUCTION_READINESS.md)
- [Release Blockers](RELEASE_BLOCKERS.md)
