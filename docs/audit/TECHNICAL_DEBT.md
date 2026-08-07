# AiOS Technical Debt Register

Audit date: 2026-08-08

## Active debt

| Priority | Debt | Next action |
| --- | --- | --- |
| P0 | Native Windows build, signing, and packaged verification are unavailable here. | Install Flutter, configure Authenticode, run clean-machine install/startup/upgrade/uninstall smoke. |
| P0 | Native token storage needs clean-account OS verification. | The Windows client now uses `flutter_secure_storage`; verify the Credential Manager entry and ACLs during release QA. |
| P1 | Handwritten migrations are safer but still lack a full versioned rollback system. | Move to Alembic or a tested versioned migration ledger. |
| P1 | Coverage is 72% overall and lifecycle modules remain weakly covered. | Add critical-module thresholds and worker/connector integration fixtures. |
| P1 | No labeled AI calibration corpus. | Add redacted labels, metrics, abstention, and drift checks. |
| P1 | Import files are bounded but unchanged files are revisited. | Add source fingerprints and an idempotent processed-source ledger. |
| P1 | Raw email retention and purge controls are not first-class UX. | Add data inventory, retention settings, export, and secure purge. |
| P2 | Flask and standalone FastAPI agents still have separate stores and status models. | Route native actions through a single authenticated core gateway over time. |
| P2 | Generic browser and GitHub adapters are MVP-depth. | Add source-specific fixtures, pagination, rate limits, and honest partial states. |
| P2 | `datetime.utcnow()` and legacy SQLAlchemy APIs produce warnings. | Migrate incrementally to timezone-aware UTC and `Session.get`. |

## Accepted for local preview

Static planner templates, local vector fallback, generic job-site selectors, lack of GitHub webhooks, and Flask browser fallback may remain in a developer preview when shown as partial capabilities. Security, signing, retention, and native verification debt may not be presented as solved for a public release.
