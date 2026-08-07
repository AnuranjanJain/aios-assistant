# AiOS Engineering Audit

Audit date: 2026-08-08

## Summary

AiOS now has a meaningful local-first hardening baseline: 109 Python tests pass, dependency audits are clean, core API boundaries are authenticated, Gmail sync has recovery behavior, background ownership is explicit, and release artifacts can be hashed and SBOM-checked. The remaining readiness gap is evidence around the native Windows package and production operations, not the original unauthenticated/local-egress design flaws.

## Evidence

- `python -m pytest -q`: 111 passed, 1 platform-dependent symlink test skipped.
- `python -m coverage run --branch -m pytest -q`: 111 passed; 72% combined coverage.
- `python scripts/ai_quality_gate.py`: passed three deterministic cases, including prompt injection.
- `python -m compileall -q app automation_agent browser_agent career_agent desktop_app.py run.py`: passed.
- `python -m pip_audit -r requirements.txt`: no known vulnerabilities.
- `python -m pip_audit -r requirements-memory.txt`: no known vulnerabilities.
- PowerShell parser check for `scripts/build-windows-native.ps1`: passed.
- Flutter, live OAuth, live Gmail, browser E2E, and packaged Windows smoke: unavailable here.

## Closed high-risk findings

| Area | Implemented control |
| --- | --- |
| Pairing | Short-lived user-approved challenge and one-time native launch secret; runtime descriptor is metadata-only. |
| AI egress | Central loopback URL validation before save and before request. |
| Agent APIs | Shared token dependency on protected FastAPI routes, plus request/field limits. |
| Browser safety | Final navigation URL validation and extension destination policy. |
| Worker ownership | Gmail is owned by the email intelligence scheduler; the opportunity monitor owns only platform/export sources. |
| SQLite | FK/WAL/busy timeout, pre-migration backup, notification claims, atomic state writes. |
| Gmail | Deletion history, transient retry/backoff, checkpoint recovery, and removed-message cleanup. |
| Inputs | Upload, import, profile, analytics, archive, and automation budgets. |
| Dependencies | Fixed declared Pillow/cryptography constraints and removed ChromaDB from the production requirements file. |
| Packaging | OAuth remains external; manifest, SHA-256, SBOM hook, and explicit signing gate. |

## Remaining engineering risks

1. Flutter 3.44.2 is now installed and the native client passes analyzer, 9 widget tests, a clean Windows build, and packaged core pairing/live smoke. High-DPI, accessibility, installer upgrade, and manual shutdown behavior still need a real desktop review.
2. Public release signing and certificate verification are not configured.
3. The migration runner is safer but still handwritten; Alembic or a versioned migration ledger with rollback should replace it.
4. Coverage is 72% overall and low in lifecycle/native/connector modules; no critical-module threshold is enforced.
5. AI quality has a deterministic smoke gate, but no redacted labeled corpus, calibration, or abstention metric.
6. WDYD remains the owner of desktop activity collection; AiOS intentionally consumes a privacy-minimized snapshot instead of silently duplicating surveillance.

## Recommendation

Approve a local developer preview. Do not label the current artifact a public production release until the native, signing, live integration, retention, and AI evaluation gates are recorded.
