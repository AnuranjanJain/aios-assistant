# AiOS Release Blockers

Audit date: 2026-08-08

| ID | Severity | Status | Evidence / next gate |
| --- | --- | --- | --- |
| RB-001 pairing token disclosure | Critical | Closed in code | One-time approval and native process-secret pairing; adversarial regression passes. |
| RB-002 remote Ollama egress | Critical | Closed in code | Loopback validation is enforced at configuration and request time. |
| RB-003 unauthenticated agent APIs | Critical | Closed in code | Shared token dependency and bounded request models are installed on all protected routes. |
| RB-004 duplicate connector execution | High | Closed in code | Desktop scheduler owns Gmail; platform/export monitor no longer scans Gmail; duplicate-ownership test passes. |
| RB-005 activity ownership | High | Resolved by scope | WDYD owns desktop activity collection; AiOS consumes a minimized snapshot and does not silently collect windows/keystrokes. |
| RB-006 unsafe schema upgrade | High | Partially closed | FK/WAL and pre-ALTER SQLite backups exist; a full versioned migration/rollback system remains. |
| RB-007 Gmail sync incompleteness | High | Closed in code | Deleted history, transient retries, checkpoint recovery, and deleted-message cleanup are implemented; live provider testing remains. |
| RB-008 unreproducible native build | High | Closed with evidence | Clean Flutter 3.44.2/Python 3.13.14 build passed on 2026-08-08; manifest and SHA-256 checksums are generated. |
| RB-009 unsigned artifacts | High | Open | Build emits an explicit unsigned marker and supports `-RequireSigning`; configure certificate thumbprint and verify Authenticode. |
| RB-010 browser redirect bypass | High | Closed in code | Final URL is validated after navigation and before extraction/download. |
| RB-011 no AI evaluation gate | High | Partially closed | Three-case deterministic gate passes; labeled corpus, calibration, and abstention thresholds remain. |
| RB-012 native verification gap | High | Partially closed | Flutter analyze, 9 widget tests, packaged core pairing/live smoke, and isolated full-payload install/uninstall smoke pass. High-DPI, accessibility, startup, and upgrade remain. |
| RB-013 triage reproducibility | High | Closed for current suite | 111 tests pass in direct and coverage runs; one platform-dependent symlink test is skipped; repeat clean subprocess runs after dependency installation remain recommended. |
| RB-014 vulnerable dependency pins | Critical | Closed for declared requirements | Both `pip-audit` requirements files report no known vulnerabilities; run the audit against the final packaged environment too. |
| RB-015 broad localhost trust | High | Closed in code | Exact origins, form/API tokens, secure cookie controls, and explicit LAN guard are implemented. |
| RB-016 notification race/state reset | High | Closed in code | Completed state stays completed and dispatch uses an atomic claim lease. |
| RB-017 unbounded work | High | Partially closed | Import, upload, analytics, browser, profile, and FastAPI limits exist; load/p95 evidence remains. |

## Public release checklist

- [x] Flutter analyzer, widget tests, build, and packaged core smoke pass.
- [x] Isolated native installer payload and uninstaller smoke pass.
- [ ] Native startup, upgrade, high-DPI, and accessibility checks pass.
- [ ] Native artifact is Authenticode-signed and signature verification is recorded.
- [ ] OAuth JSON is external and absent from the executable/archive.
- [ ] Live Gmail multi-account, expiry, deletion, and rate-limit fixtures pass.
- [ ] Redacted AI evaluation corpus meets agreed precision/recall/calibration thresholds.
- [ ] OS ACL, retention, export, purge, accessibility, and high-DPI checks pass.
