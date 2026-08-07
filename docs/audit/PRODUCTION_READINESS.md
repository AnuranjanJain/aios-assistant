# AiOS Production Readiness

Audit date: 2026-08-08

## Score: 89/100

| Dimension | Weight | Score | Current evidence |
| --- | ---: | ---: | --- |
| Core correctness | 20 | 17 | 116 tests pass, with one platform-dependent symlink test skipped; Gmail deletion/retry, bounded imports, scheduler ownership, and native UI behavior are covered. |
| Security and privacy | 20 | 18 | Pairing, local-AI egress, agent auth, CORS, extension destinations, upload sanitization, dependency gates, and Windows secure token storage are implemented. OS ACL verification remains. |
| Reliability and data integrity | 15 | 15 | SQLite FK/WAL, checksummed named migrations, consistent pre-upgrade backup, explicit offline restore, atomic state, notification claims, and cursor recovery are covered by tests. |
| Performance and scalability | 15 | 13 | Request/import/analytics limits and provider retry budgets exist. Synthetic 10k-message warm reads pass with `/api/live` p95 213.67 ms and inbox p95 23.83 ms; 100k/24-hour evidence remains. |
| AI quality and safety | 10 | 9 | Untrusted-content boundaries, clamped confidence, category metrics, calibration error, abstention thresholds, and prompt-injection safety pass on 16 redacted synthetic cases. Consent-based real labels remain. |
| Native UX and accessibility | 10 | 8 | Flutter analyzer, 10 widget tests including high-DPI layout, compact-layout checks, and packaged-core pairing smoke pass. Screen-reader, forced-colors, and manual keyboard review remain. |
| Release and operations | 10 | 9 | Clean Windows build, 18-file manifest, SHA-256 checksums, CycloneDX SBOM, installer payload, and packaged smoke pass. The artifact is intentionally unsigned. |
| **Total** | **100** | **89** | **Strong local release candidate; public release still needs signing, external integration evidence, OS privacy verification, and manual accessibility review** |

## Go/no-go

**Go for local release-candidate testing. No-go for public production release.** The native build, packaged core, migration rollback, AI gate, and synthetic performance budget are verified. A 100 score would be dishonest without a trusted signing certificate, live connector fixtures, OS privacy verification, and accessibility evidence.

## Required before 100

- Verified Windows install, startup, upgrade, uninstall, high-DPI, keyboard, screen-reader, forced-colors, and reduced-motion runs against the release bundle.
- Authenticode-signed EXE plus verified signature and release provenance.
- OS credential/ACL checks and user-facing retention/export/purge controls.
- Redacted AI evaluation corpus with enforced category and confidence metrics.
- Repeatable live Gmail, GitHub, and browser integration fixtures.
