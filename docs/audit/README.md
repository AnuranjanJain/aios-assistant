# AiOS Production Readiness Audit

Audit date: 2026-08-08

## Current verdict

**Evidence score: 91/100.** The critical local-security, duplicate-worker, migration, bounded-work, deterministic AI-gate, and local privacy-control findings are addressed in this worktree. AiOS is a strong local release candidate: the source suite is green, a synthetic 100k-message benchmark passes, and the packaged core evidence is retained, but the current plugin-enabled native shell needs a fresh build after Windows Developer Mode is enabled. It is not an honest 100/100 public release until signing, live connector fixtures, OS privacy verification, and manual accessibility review exist.

## Evidence snapshot

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 124 passed, 1 platform-dependent symlink test skipped |
| `python -m coverage run --branch -m pytest -q` | 124 passed; 69% combined coverage |
| `python -m compileall -q ...` | Passed |
| `python -m pip_audit -r requirements.txt` | No known vulnerabilities |
| `python -m pip_audit -r requirements-memory.txt` | No known vulnerabilities |
| `scripts/ai_quality_gate.py` | Passed: 16 redacted synthetic cases; macro F1 1.00, actionable F1 1.00, ECE 0.1869, abstention 0.125 |
| `scripts/performance_smoke.py --dataset-size 100000 --samples 7` | Passed: `/api/live` p95 265.51 ms, inbox p95 50.10 ms |
| Versioned migration/rollback test | Passed: named ledger, checksum validation, consistent backup, explicit restore, idempotent rerun |
| PowerShell build-script parse | Passed |
| Flutter analyzer | Passed: Flutter 3.44.2 |
| Flutter widget tests | Passed: 10 tests, including high-DPI layout |
| Windows native build | Source/native tests passed; fresh plugin-enabled rebuild blocked by missing Windows Developer Mode symlink support |
| Packaged core pairing/live smoke | Passed: authenticated `/api/live`, no leftover process/port/temp data |
| Isolated installer lifecycle smoke | Passed: full UI/core payload copied to `%TEMP%`, exact uninstaller removed it |
| Native installer startup path | Passed directly against the current native build output under `%TEMP%`; the checked-in smoke script will verify the same path after a fresh release rebuild |
| Native first-run readiness | Essential and optional setup checks are surfaced in the native Overview, with direct links to Gmail, Workers, Settings, and Memory |
| Release metadata | Historical candidate has an 18-file manifest, SHA-256 checksums, CycloneDX SBOM, and explicit unsigned marker; the current verifier rejects that stale manifest because it lacks source provenance |
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
- A repeatable synthetic performance smoke measures warm dashboard reads against 100,000 stored messages.
- OAuth JSON stays external in `%APPDATA%\AiOS Assistant\credentials`; it is never embedded in a release executable.
- The Windows build produces a manifest, SHA-256 file, CycloneDX SBOM when `pip-audit` is installed, and an explicit unsigned-build marker.
- The native bearer token is stored in Windows secure storage; JSON preferences retain only non-secret UI/API metadata. Legacy JSON tokens migrate on the next successful start.
- The native client now requires the current core contract version before
  accepting an existing local runtime, preventing a newer shell from silently
  using a stale installed backend.
- Essential readiness checks now distinguish optional Ollama/GitHub setup from
  the Gmail and worker path required for live daily planning. Worker failures
  are surfaced as attention states.

## Remaining release gates

1. Run native startup, high-DPI, keyboard, screen-reader, forced-colors, and reduced-motion checks on a real Windows desktop; isolated install/upgrade/uninstall/startup smoke already passes.
2. Configure Authenticode signing and run `scripts/build-windows-native.ps1 -RequireSigning`.
3. Verify OS ACLs and run the final native shell accessibility checklist.
4. Replace the synthetic AI fixture with consented redacted labels and compare drift over time.
5. Run live Gmail multi-account, OAuth-expiry, GitHub-rate-limit, and browser redirect fixtures.

The desktop activity collector remains owned by the What Do You Do companion boundary. AiOS consumes its privacy-minimized activity snapshot; it does not silently duplicate keystroke/window surveillance.

Settings now exposes a data inventory, secret-redacted local export, scoped purge controls, and operational-history retention cleanup. Purge is explicit and requires confirmation.

## Reports

- [Engineering Audit](ENGINEERING_AUDIT.md)
- [Technical Debt](TECHNICAL_DEBT.md)
- [Security](SECURITY_REPORT.md)
- [Performance](PERFORMANCE_REPORT.md)
- [AI Quality](AI_QUALITY_REPORT.md)
- [UX](UX_REPORT.md)
- [Production Readiness](PRODUCTION_READINESS.md)
- [Release Blockers](RELEASE_BLOCKERS.md)
