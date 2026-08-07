# AiOS Performance Report

Audit date: 2026-08-08

## Current evidence

The Python suite completes 109 tests in roughly 30 seconds on this workstation. Branch coverage is 72% combined. This is a correctness signal, not a production load benchmark. No large-mailbox, memory, CPU, packaged startup, or native UI benchmark has been run.

## Implemented budgets

- Flask uploads: 25 MB global cap; profile images: 5 MB and 1024px normalized output.
- JSON/mailbox/import sources: 50 MB and 5,000-record safety budgets where applicable.
- Analytics: bounded metric/repository windows and ordered latest-activity reads.
- FastAPI agents: 256 KB request body cap plus bounded text fields and parameter maps.
- Browser: bounded pages/results and final URL checks.
- Gmail: transient retry/backoff, deletion handling, and checkpoint restoration.
- Notifications: atomic short-lived claims prevent concurrent duplicate delivery.
- Worker state/runtime descriptors: atomic replace writes; desktop runtime owns background loops.

## Remaining performance risks

**PERF-001: no p95 or large-dataset evidence.** Dashboard projections, local vector fallback, GitHub analysis, and Gmail analysis are suitable for a personal dataset but not yet measured at 10k/100k messages.

**PERF-002: source files are still revisited.** Platform and job-import connectors are bounded and idempotent at the record level, but a fingerprint ledger would reduce repeated parsing for unchanged files.

**PERF-003: synchronous projections.** Email views, planning summaries, and dashboard reads can still do materialization work in the request path. A durable snapshot/job ledger is the next scale improvement.

**PERF-004: lifecycle coverage is uneven.** Workers, notifications, browser tools, and native startup have lower module coverage than the intelligence paths; the CI workflow currently runs tests and audits but has no critical-module threshold.

## Benchmark plan before public release

Measure cold/warm startup, native discovery, dashboard p50/p95 latency, 10k and 100k stored messages, 1/5/20 Gmail accounts, memory after 24 hours, provider outage recovery, import throughput, and duplicate notification rate. Record CPU, RSS, database size, API latency, provider calls, and retry counts.
