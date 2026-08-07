# AiOS Technical Debt Register

Audit date: 2026-08-08

## Active debt

| Priority | Debt | Next action |
| --- | --- | --- |
| P0 | Native Windows build, signing, and packaged verification are unavailable here. | Install Flutter, configure Authenticode, run clean-machine install/startup/upgrade/uninstall smoke. |
| P0 | Native token storage needs clean-account OS verification. | The Windows client now uses `flutter_secure_storage`; verify the Credential Manager entry and ACLs during release QA. |
| P1 | The explicit SQLite migration ledger is covered, but it remains a small hand-maintained runner rather than Alembic. | Keep checksum/idempotency/rollback tests green; migrate to Alembic only when multi-device schema history needs it. |
| P1 | Coverage is 73% overall and lifecycle modules remain weakly covered. | Add critical-module thresholds and worker/connector integration fixtures. |
| P1 | The deterministic AI gate uses a synthetic redacted corpus; it is not a user-labeled accuracy claim. | Add consented redacted labels, deadline/notification metrics, and drift checks. |
| P1 | Performance has a synthetic 10k p95 baseline but no 100k/24-hour evidence. | Add a scheduled scale run with CPU, RSS, database size, retry, and notification-duplication measurements. |
| P1 | Import files are bounded but unchanged files are revisited. | Add source fingerprints and an idempotent processed-source ledger. |
| P1 | Raw email retention and purge controls are not first-class UX. | Add data inventory, retention settings, export, and secure purge. |
| P2 | Flask and standalone FastAPI agents still have separate stores and status models. | Route native actions through a single authenticated core gateway over time. |
| P2 | Generic browser and GitHub adapters are MVP-depth. | Add source-specific fixtures, pagination, rate limits, and honest partial states. |
| P2 | `datetime.utcnow()` and legacy SQLAlchemy APIs produce warnings. | Migrate incrementally to timezone-aware UTC and `Session.get`. |

## Accepted for local preview

Static planner templates, local vector fallback, generic job-site selectors, lack of GitHub webhooks, and Flask browser fallback may remain in a developer preview when shown as partial capabilities. Security, signing, retention, and native verification debt may not be presented as solved for a public release.
