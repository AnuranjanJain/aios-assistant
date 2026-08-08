# AiOS Production Readiness

Audit date: 2026-08-08

## Score: 91/100

| Dimension | Weight | Score | Current evidence |
| --- | ---: | ---: | --- |
| Core correctness | 20 | 18 | 124 tests pass, with one platform-dependent symlink test skipped; Gmail deletion/retry, bounded imports, scheduler ownership, privacy controls, and native UI behavior are covered. |
| Security and privacy | 20 | 19 | Pairing, local-AI egress, agent auth, CORS, extension destinations, upload sanitization, dependency gates, secure token storage, redacted export, scoped purge, and bounded retention are implemented. OS ACL verification remains. |
| Reliability and data integrity | 15 | 15 | SQLite FK/WAL, checksummed named migrations, consistent pre-upgrade backup, explicit offline restore, atomic state, notification claims, and cursor recovery are covered by tests. |
| Performance and scalability | 15 | 14 | Request/import/analytics limits and provider retry budgets exist. Synthetic 100k-message warm reads pass with `/api/live` p95 265.51 ms and inbox p95 50.10 ms; 24-hour/provider-scale evidence remains. |
| AI quality and safety | 10 | 9 | Untrusted-content boundaries, clamped confidence, category metrics, calibration error, abstention thresholds, and prompt-injection safety pass on 16 redacted synthetic cases. Consent-based real labels remain. |
| Native UX and accessibility | 10 | 8 | Flutter analyzer, 10 widget tests including high-DPI layout, compact-layout checks, and packaged-core pairing smoke pass. Screen-reader, forced-colors, and manual keyboard review remain. |
| Release and operations | 10 | 8 | Previous clean Windows build, manifest, SHA-256 checksums, CycloneDX SBOM, installer payload, packaged smoke, and isolated startup-install check pass. The current plugin-enabled native rebuild is blocked by missing Developer Mode, and artifacts are unsigned. |
| **Total** | **100** | **91** | **Strong local release candidate; public release still needs a fresh native build, signing, external integration evidence, OS privacy verification, and manual accessibility review** |

## Go/no-go

**Go for local release-candidate testing. No-go for public production release.** The source suite, packaged core, migration rollback, AI gate, synthetic performance budget, and privacy controls are verified. A 100 score would be dishonest without a trusted signing certificate, live connector fixtures, OS privacy verification, and accessibility evidence.

## Required before 100

- Verified Windows install, startup, upgrade, uninstall, high-DPI, keyboard, screen-reader, forced-colors, and reduced-motion runs against the release bundle.
- Authenticode-signed EXE plus verified signature and release provenance.
- OS credential/ACL checks and manual accessibility evidence.
- Redacted AI evaluation corpus with enforced category and confidence metrics.
- Repeatable live Gmail, GitHub, and browser integration fixtures.
