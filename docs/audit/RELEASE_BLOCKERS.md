# AiOS Release Blockers

Audit date: 2026-08-08

| ID | Severity | Status | Evidence / next gate |
| --- | --- | --- | --- |
| RB-001 pairing token disclosure | Critical | Closed in code | One-time approval and native process-secret pairing; adversarial regression passes. |
| RB-002 remote Ollama egress | Critical | Closed in code | Loopback validation is enforced at configuration and request time. |
| RB-003 unauthenticated agent APIs | Critical | Closed in code | Shared token dependency and bounded request models are installed on all protected routes. |
| RB-004 duplicate connector execution | High | Closed in code | Desktop scheduler owns Gmail; platform/export monitor no longer scans Gmail; duplicate-ownership test passes. |
| RB-005 activity ownership | High | Resolved by scope | WDYD owns desktop activity collection; AiOS consumes a minimized snapshot and does not silently collect windows/keystrokes. |
| RB-006 unsafe schema upgrade | High | Closed with evidence | Named checksummed migration steps, one consistent pre-upgrade backup, checksum refusal, explicit offline restore, and idempotent upgrade/restore tests pass. |
| RB-007 Gmail sync incompleteness | High | Closed in code | Deleted history, transient retries, checkpoint recovery, and deleted-message cleanup are implemented; live provider testing remains. |
| RB-008 unreproducible native build | High | Closed with evidence | Clean Flutter 3.44.2/Python 3.13.14 build passed on 2026-08-08; manifest and SHA-256 checksums are generated. |
| RB-009 unsigned artifacts | High | Open | Build emits an explicit unsigned marker and supports `-RequireSigning`; configure certificate thumbprint and verify Authenticode. |
| RB-010 browser redirect bypass | High | Closed in code | Final URL is validated after navigation and before extraction/download. |
| RB-011 no AI evaluation gate | High | Partially closed | Sixteen redacted synthetic cases pass macro F1 1.00, actionable F1 1.00, ECE 0.1869, abstention 0.125, and prompt-injection safety. Consent-based user labels and drift monitoring remain. |
| RB-012 native verification gap | High | Partially closed | Flutter analyze, 10 widget tests including high-DPI layout, packaged core pairing/live smoke, and isolated install/upgrade/uninstall smoke pass. Real-desktop accessibility, keyboard, forced-colors, and manual shutdown review remain. |
| RB-013 triage reproducibility | High | Closed for current suite | 116 tests pass in the direct and coverage runs; one platform-dependent symlink test is skipped; repeat clean subprocess runs after dependency installation remain recommended. |
| RB-014 vulnerable dependency pins | Critical | Closed for declared requirements | Both `pip-audit` requirements files report no known vulnerabilities; run the audit against the final packaged environment too. |
| RB-015 broad localhost trust | High | Closed in code | Exact origins, form/API tokens, secure cookie controls, and explicit LAN guard are implemented. |
| RB-016 notification race/state reset | High | Closed in code | Completed state stays completed and dispatch uses an atomic claim lease. |
| RB-017 unbounded work | High | Closed with bounded evidence | Import, upload, analytics, browser, profile, and FastAPI limits plus provider retry budgets exist; synthetic 10k-message warm reads pass with `/api/live` p95 213.67 ms and inbox p95 23.83 ms. 100k/24-hour/live-account measurements remain. |

## Public release checklist

- [x] Flutter analyzer, widget tests, build, and packaged core smoke pass.
- [x] Isolated native installer payload and uninstaller smoke pass.
- [ ] Native startup, high-DPI, keyboard, screen-reader, forced-colors, and reduced-motion checks pass on a real desktop.
- [ ] Native artifact is Authenticode-signed and signature verification is recorded.
- [ ] OAuth JSON is external and absent from the executable/archive.
- [ ] Live Gmail multi-account, expiry, deletion, and rate-limit fixtures pass.
- [x] Synthetic redacted AI gate meets precision/recall/calibration/abstention thresholds.
- [ ] Consent-based real AI labels and drift checks meet the same thresholds.
- [ ] OS ACL, retention, export, purge, accessibility, and high-DPI checks pass.
