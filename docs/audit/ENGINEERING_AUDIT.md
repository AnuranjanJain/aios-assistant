# AiOS Engineering Audit

Audit date: 2026-08-08

## Summary

AiOS now has a meaningful local-first hardening baseline: 124 Python tests pass, dependency audits are clean, core API boundaries are authenticated, Gmail sync has recovery behavior, background ownership is explicit, migrations are checksummed and rollback-tested, privacy inventory/export/purge controls are covered, and release artifacts can be hashed and SBOM-checked. The remaining readiness gap is evidence around signing, real integrations, native accessibility, and production operations, not the original unauthenticated/local-egress design flaws.

## Evidence

- `python -m pytest -q`: 124 passed, 1 platform-dependent symlink test skipped.
- `python -m coverage run --branch -m pytest -q`: 124 passed; 69% combined coverage.
- `python scripts/ai_quality_gate.py`: passed 16 redacted synthetic cases; macro F1 1.00, actionable F1 1.00, ECE 0.1869, abstention 0.125, prompt injection safe.
- `python scripts/performance_smoke.py --dataset-size 100000 --samples 7`: passed synthetic 100,000-message benchmark; `/api/live` p95 265.51 ms and inbox p95 50.10 ms.
- `python -m compileall -q app automation_agent browser_agent career_agent desktop_app.py run.py`: passed.
- `python -m pip_audit -r requirements.txt`: no known vulnerabilities.
- `python -m pip_audit -r requirements-memory.txt`: no known vulnerabilities.
- PowerShell parser check for `scripts/build-windows-native.ps1`: passed.
- Flutter analyzer/widget tests pass; a fresh plugin-enabled Windows rebuild is blocked here by missing Developer Mode symlink support. Live OAuth, live Gmail, and browser E2E remain unavailable.

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

1. Flutter 3.44.2 is now installed and the native client passes analyzer, 10 widget tests including high-DPI layout, a clean Windows build, packaged core pairing/live smoke, and isolated install/upgrade/uninstall smoke. Accessibility and manual shutdown behavior still need a real desktop review.
2. Public release signing and certificate verification are not configured.
3. The migration runner is now a checksummed versioned ledger with explicit offline rollback; Alembic remains a future multi-device option.
4. Coverage is 69% overall and low in lifecycle/native/connector modules; no critical-module threshold is enforced.
5. AI quality has a deterministic synthetic gate with calibration and abstention metrics, but no consented user-labeled corpus or drift measurement.
6. WDYD remains the owner of desktop activity collection; AiOS intentionally consumes a privacy-minimized snapshot instead of silently duplicating surveillance.
7. Privacy controls now include secret-redacted export, scoped deletion, and operational-history retention cleanup; OS ACL behavior still requires clean-account verification.

## Recommendation

Approve a local developer preview. Do not label the current artifact a public production release until the native, signing, live integration, retention, and AI evaluation gates are recorded.
