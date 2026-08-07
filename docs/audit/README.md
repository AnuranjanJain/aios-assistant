# AiOS Production Readiness Audit

Audit date: 2026-08-08

## Current verdict

**Evidence score: 84/100.** The critical local-security and duplicate-worker findings from the first audit are addressed in this worktree. AiOS is now a verified local release candidate: the Windows artifact builds, pairs, serves authenticated data, and cleans up correctly. It is not an honest 100/100 public release until signing, live connector fixtures, and the remaining quality/accessibility evidence exist.

## Evidence snapshot

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 111 passed, 1 platform-dependent symlink test skipped |
| `python -m coverage run --branch -m pytest -q` | 111 passed; 72% combined coverage |
| `python -m compileall -q ...` | Passed |
| `python -m pip_audit -r requirements.txt` | No known vulnerabilities |
| `python -m pip_audit -r requirements-memory.txt` | No known vulnerabilities |
| `scripts/ai_quality_gate.py` | Passed: 3 deterministic cases, including prompt injection |
| PowerShell build-script parse | Passed |
| Flutter analyzer | Passed: Flutter 3.44.2 |
| Flutter widget tests | Passed: 9 tests |
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
- Imports, analytics, profile images, browser redirects, extension destinations, and agent request bodies are bounded.
- OAuth JSON stays external in `%APPDATA%\AiOS Assistant\credentials`; it is never embedded in a release executable.
- The Windows build produces a manifest, SHA-256 file, CycloneDX SBOM when `pip-audit` is installed, and an explicit unsigned-build marker.
- The native bearer token is stored in Windows secure storage; JSON preferences retain only non-secret UI/API metadata. Legacy JSON tokens migrate on the next successful start.

## Remaining release gates

1. Run native startup, upgrade, high-DPI, and accessibility checks on the release bundle; isolated install/uninstall smoke already passes.
2. Configure Authenticode signing and run `scripts/build-windows-native.ps1 -RequireSigning`.
3. Add OS ACL verification, retention/purge UX, and accessibility/high-DPI checks.
4. Build a redacted labeled AI corpus and enforce precision, recall, calibration, and abstention thresholds.
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
