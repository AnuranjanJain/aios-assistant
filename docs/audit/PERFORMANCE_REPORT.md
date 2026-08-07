# AiOS Performance Report

Audit date: 2026-08-08

## Current evidence

The Python suite completes 124 tests in roughly 52 seconds on this workstation. Branch coverage is 69% combined. The default synthetic 10,000-message SQLite benchmark measures warm dashboard reads without touching user data; an explicit 100,000-message run is recorded below.

### Synthetic benchmark evidence

`python scripts/performance_smoke.py` passed on 2026-08-08 with 15 samples per route and a 1,500 ms p95 budget:

| Route | p50 | p95 | Max |
| --- | ---: | ---: | ---: |
| `/api/live` | 192.32 ms | 228.02 ms | 251.86 ms |
| `/api/inbox/overview` | 20.78 ms | 27.29 ms | 27.49 ms |

The fixture is synthetic metadata only; it is evidence for bounded local dashboard reads, not a 100k-message or 24-hour memory claim.

The same harness also passed a 100,000-message run with 7 samples per route:

| Route | p50 | p95 | Max |
| --- | ---: | ---: | ---: |
| `/api/live` | 262.68 ms | 265.51 ms | 266.18 ms |
| `/api/inbox/overview` | 47.47 ms | 50.10 ms | 50.98 ms |

This closes the 100k warm-read gate. Provider outage recovery, multi-account load, and 24-hour memory/CPU behavior remain operational tests.

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

**PERF-001: scale evidence is incomplete.** The 100k warm dashboard benchmark passes, but dashboard projections, local vector fallback, GitHub analysis, and Gmail analysis are not yet measured after 24 hours.

**PERF-002: source files are still revisited.** Platform and job-import connectors are bounded and idempotent at the record level, but a fingerprint ledger would reduce repeated parsing for unchanged files.

**PERF-003: synchronous projections.** Email views, planning summaries, and dashboard reads can still do materialization work in the request path. A durable snapshot/job ledger is the next scale improvement.

**PERF-004: lifecycle coverage is uneven.** Workers, notifications, browser tools, and native startup have lower module coverage than the intelligence paths; the CI workflow currently runs tests and audits but has no critical-module threshold.

## Benchmark plan before public release

Measure cold/warm startup, native discovery, dashboard p50/p95 latency at 100k stored messages, 1/5/20 Gmail accounts, memory after 24 hours, provider outage recovery, import throughput, and duplicate notification rate. Record CPU, RSS, database size, API latency, provider calls, and retry counts.
