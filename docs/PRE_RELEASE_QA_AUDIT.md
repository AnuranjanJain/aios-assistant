# AiOS Agent Pre-Release Validation and QA Audit

Date: 2026-06-16
Scope: Flask dashboard, native desktop launcher, Memory Agent, Planner Agent, Desktop Automation Agent, Browser Automation Agent, Career Copilot, connectors, workers, local API surface.

## Already Completed Checks Skipped

The following checks were not repeated because they were already completed in the immediately preceding validation pass:

- Full unit/integration suite: `python -m pytest -q` passed with `14 passed`.
- Dependency audit: `python -m pip_audit -r requirements.txt` found no known vulnerabilities.
- Windows executable rebuild succeeded.
- Packaged `/career` and `/api/career` returned HTTP 200.
- Career Copilot screenshot was captured and added to README.

## Final Output

Production Readiness Score: **68 / 100**

Release Recommendation: **REJECT RELEASE**

Reason: the app is promising and most screens load, but the audit found release-blocking reliability and security issues:

- Memory writes block on per-item Ollama embedding attempts and failed stress targets.
- Local pairing endpoint can expose `LOCAL_API_TOKEN` to loopback callers.
- Some API endpoints accept empty payloads and write low-value data.
- Accessibility has unlabeled controls in Planner and Sources.
- Several fallback paths are only partial and need explicit user-facing failure states.

## Phase 1 - System Inventory

### Frontend Modules

| Module | Purpose | Dependencies | Failure Impact |
| --- | --- | --- | --- |
| `dashboard.html` | Main workspace dashboard | Flask routes, `/api/live`, `app.js`, SQLite data | User loses central command view |
| `mobile.html` | Phone/LAN dashboard | Flask routes, `/api/live`, PWA assets | Mobile monitoring unusable |
| `memory.html` | Persistent memory UI | Memory service, vector ranking, SQLite | User cannot inspect or add memory |
| `planner.html` | Goal planner UI | Goal planner service, memory entities | Roadmap tracking unavailable |
| `automation.html` | Desktop automation UI | Automation engine, local filesystem tools | File/office automation unavailable |
| `browser_agent.html` | Browser automation UI | Browser engine, Playwright | Job research automation unavailable |
| `career.html` | Career Copilot UI | Career engine, SQLite career graph | Career scoring and applications unavailable |
| `connectors.html` | Gmail/import connector UI | Google OAuth/local import services | Live inbox/opportunity sync unavailable |
| `settings.html` | Runtime settings and PIN | Settings/auth services | User cannot configure local integrations |
| `workers.html` | Background service controls | Worker subprocess manager | Background sync cannot be controlled |

### Backend Modules

| Module | Purpose | Dependencies | Failure Impact |
| --- | --- | --- | --- |
| `app/routes.py` | Main Flask routes and API | Flask, services, SQLAlchemy | App request surface fails |
| `app/models.py` | SQLAlchemy app database | SQLite | Core data persistence fails |
| `app/services/memory_engine.py` | Memory graph, facts, search | SQLite, Ollama embeddings optional | Memory/search slow or unavailable |
| `app/services/goal_planner.py` | Goal roadmap and task tracking | Memory entities, SQLite | Planner unusable |
| `app/services/connectors.py` | Gmail, local imports, job/hackathon imports | Google OAuth, local files | External data ingestion fails |
| `app/services/workers.py` | Worker process lifecycle | subprocess, state JSON | Background services unreliable |
| `automation_agent/*` | Local desktop automation | filesystem, office libs, OCR, SQLite | Automation unavailable or unsafe |
| `browser_agent/*` | Browser research and job tracking | Playwright, domain safety, SQLite | Browser automation unavailable |
| `career_agent/*` | Career intelligence and graph | SQLite, optional GitHub API | Career Copilot unavailable |

### APIs and Routes

Safe GET route sweep:

- HTML routes checked: 12
- API GET routes checked: 19
- Result: all non-parameterized safe GET pages returned 200 except `/api/memory/search`, which returned expected 400 without `q`.

Key mutable APIs:

- Planner: `/api/planner`, `/api/planner/tasks/<id>`, `/planner`
- Memory: `/api/memory/entities`, `/api/memory/facts`, `/api/memory/checkpoints`, `/api/memory/relations`
- Automation: `/automation/plan`, `/automation/plans/<id>/execute`
- Browser Agent: `/browser-agent/plan`, `/browser-agent/plans/<id>/execute`
- Career: `/career/github/analyze`, `/career/resume/optimize`, `/career/jobs/match`, `/career/applications`
- Connectors: `/api/connectors/<id>/run`, `/connectors/<id>/run`
- Wellbeing: `/api/wellbeing/activity`

### Database Tables

Main SQLAlchemy DB:

- `Opportunity`
- `Reminder`
- `InboxItem`
- `ActivityEvent`
- `AgentDecision`
- `ConnectorRun`
- `HackathonUpdate`
- `PlacementUpdate`
- `Setting`
- `MemoryEntity`
- `MemoryFact`
- `MemoryRelation`
- `WorkCheckpoint`
- `GoalPlan`
- `PlanTask`
- `PlanTaskSession`

Agent SQLite DBs:

- Automation: `automation_plan`, `automation_action`
- Browser: `browser_plan`, `browser_action`, `job_opportunity`, `job_application`
- Career: `career_profile`, `github_repository`, `project_profile`, `graph_node`, `graph_edge`, `resume_version`, `job_match`, `career_application`, `career_recommendation`, `vector_document`

### Configuration and Environment Variables

Important variables:

- Core: `SECRET_KEY`, `DATABASE_URL`, `HOST`, `PORT`, `AIOS_DATA_DIR`
- AI: `AI_PROVIDER`, `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL`, `MEMORY_VECTOR_BACKEND`, `MEMORY_VECTOR_PATH`
- Cloud keys: `GEMINI_API_KEY`, `OPENAI_API_KEY`
- Gmail: `GMAIL_MBOX_PATH`, `GMAIL_OPPORTUNITY_QUERY`, `GMAIL_HACKATHON_QUERY`
- Imports: `JOB_PORTAL_IMPORT_DIR`, `HACKATHON_IMPORT_DIR`, `WATCH_IMPORT_DIR`
- Workers: `HACKATHON_SCAN_INTERVAL_MINUTES`
- Local API: `LOCAL_API_TOKEN`
- Automation: `AIOS_AUTOMATION_ALLOWED_ROOTS`, `AIOS_DESKTOP_CONTROL_ENABLED`
- Browser: `AIOS_BROWSER_ALLOWED_DOMAINS`, `AIOS_BROWSER_HEADLESS`
- Career: `GITHUB_TOKEN`, `AIOS_CAREER_PROJECTS`

### External Dependencies

- Flask, SQLAlchemy, PyWebView
- Google API client and OAuth libraries
- FastAPI and Uvicorn for agent APIs
- python-docx, python-pptx, openpyxl
- Pillow, pytesseract
- PyAutoGUI, xdotool on Linux
- Playwright
- Optional Ollama local model server
- Optional GitHub API token
- Optional Gmail OAuth credentials

### System Dependency Map

| Module | Purpose | Dependencies | Failure Impact |
| --- | --- | --- | --- |
| Flask app | Unified UI/API shell | templates, services, SQLite | Whole app unavailable |
| Memory Agent | Durable personal memory | SQLite, optional Ollama embedding | Search and resume context degrade |
| Planner Agent | Goal decomposition and progress | Memory Agent, SQLite | Plans cannot adapt to progress |
| Desktop Automation Agent | Local task execution | allowed roots, approval tokens, office/OCR tools | Unsafe automation if boundaries fail |
| Browser Automation Agent | Browser research and job tracking | Playwright, domain allowlist | Research fails or external side effects risk |
| Career Copilot | Career graph and recommendations | GitHub/local repo scan, SQLite | Career Brain unavailable |
| Connectors | Gmail/import/job/hackathon ingestion | OAuth, local files, SQLite | Dashboard loses real data |
| Workers | Background sync | subprocesses, worker state JSON | No continuous ingestion |
| What Do You Do integration | Wellbeing/activity input | local token API, CORS allowlist | Activity metrics incomplete |

## Phase 2 - Test Coverage Audit

| Component | Current Coverage | Missing Coverage | Risk Level |
| --- | --- | --- | --- |
| Memory Agent | Unit tests exist | Stress, Ollama-offline write latency, migration tests | High |
| Planner Agent | Unit tests exist | E2E form workflow, malformed task updates | Medium |
| Desktop Automation Agent | Unit tests exist | Real file permission scenarios, Linux xdotool, LibreOffice missing | High |
| Browser Agent | Unit tests exist | Real Playwright browser failure, CAPTCHA/login pages, download handling | High |
| Career Copilot | Unit tests exist | GitHub API failure cache, resume import/export, large application DB | Medium |
| Connectors | Partial manual testing | OAuth expiry, missing Gmail API, malformed imports, duplicate imports | High |
| UI | Route smoke tests | Click-by-click E2E workflow, keyboard-only navigation, visual regression | Medium |
| Security | Static probes and auth checks | Token exfiltration tests, path fuzzing, prompt injection suite | High |
| Performance | Smoke/stress probes | Repeatable benchmark harness and thresholds | High |

## Phase 3 - UI Validation

Screens checked by route and responsive probe:

- `/`
- `/mobile`
- `/automation`
- `/browser-agent`
- `/career`
- `/connectors`
- `/memory`
- `/planner`
- `/settings`
- `/sources`
- `/workers`
- `/login`

Findings:

| ID | Severity | Area | Finding | Fix |
| --- | --- | --- | --- | --- |
| UI-1 | Medium | Planner | Cadence `select` is not wrapped in a label and has no `aria-label`. | Add visible label or `aria-label`. |
| UI-2 | Medium | Sources | File input is unlabeled. | Wrap file input in label with visible text. |
| UI-3 | Low | Dashboard | Static scan found `outline: 0` declarations. Some focus styles exist, but global focus behavior needs manual keyboard verification. | Add consistent `:focus-visible` styles. |

Positive results:

- No console errors in sampled pages.
- No horizontal overflow found in sampled pages.
- Buttons/forms were present and rendered.
- Empty-state isolated DB pages loaded without crashing.

## Phase 4 - Navigation Audit

Safe GET route results:

| Category | Count | Result |
| --- | ---: | --- |
| HTML routes | 12 | All returned 200 |
| API GET routes | 19 | 18 returned 200; `/api/memory/search` returned expected 400 without query |
| Template `url_for` references | scanned | No missing endpoint found during render smoke |

Broken Route Report:

| Route | Finding | Severity |
| --- | --- | --- |
| `/api/memory/search` without `q` | Returns 400 as expected | None |
| Parameterized routes | Not exhaustively fuzzed in this pass | Medium residual risk |

## Phase 5 - Vertical Options Strip Bug

Issue from PDF: vertical strip appears and only one letter is visible.

Reproduction attempts:

- Dashboard, mobile dashboard, automation, browser agent, career, connectors, memory, planner
- Viewports: 390x844, 768x1024, 1366x768, 1920x1080

Result: **Not reproduced**

Evidence:

- No horizontal overflow detected.
- No tall skinny visible `aside`, `nav`, `.sidebar`, `.menu`, `.nav-label`, or `.nav-initial` elements detected.
- No console errors.

Root Cause Analysis:

- The most likely historical cause is sidebar/nav width collapse or an icon/text fallback issue.
- Current code includes narrow `.nav-initial` elements by design, but the probe did not find them rendered as a broken vertical strip.
- The dashboard template previously had a mojibake settings icon in the remembered diff, but current rendered template shows `⚙`.

Verification Tests:

- Automated viewport matrix passed for sampled pages.
- Still needs manual visual verification inside the native PyWebView shell at Windows scaling values like 125 percent and 150 percent.

Before/After Impact:

- Before: suspected collapsed sidebar could make navigation unusable.
- Current: no reproduced defect in browser viewport matrix.
- Residual impact: native WebView scaling may differ from Chromium test viewport.

## Phase 6 - Empty State Validation

Isolated empty database probe:

| Route | Status | Load Time |
| --- | ---: | ---: |
| `/` | 200 | 27.7 ms |
| `/mobile` | 200 | 10.1 ms |
| `/memory` | 200 | 21.5 ms |
| `/planner` | 200 | 25.3 ms |
| `/automation` | 200 | 65.4 ms |
| `/browser-agent` | 200 | 42.3 ms |
| `/career` | 200 | 523.7 ms |
| `/api/live` | 200 | 2.4 ms |
| `/api/career` | 200 | 20.6 ms |

Findings:

- Empty state does not crash.
- Career first load is slower because it bootstraps seeded placeholder projects and recommendations.
- Some empty states are generic; guidance can be improved for first-run setup.

## Phase 7 - Fallback Conditions

| Condition | Fallback | User Impact | Recovery Method | Status |
| --- | --- | --- | --- | --- |
| Memory write with Ollama offline/slow | Catches embedding error after timeout | Severe latency on many writes | Add fast offline embedding skip/cache | Fails stress target |
| Database failure | SQLAlchemy errors likely propagate in some paths | User sees failed request | Add retry/read-only degraded mode | Partial |
| Ollama offline for classifier | Rule-based classifier fallback exists | Lower quality classification | Inform user in UI | Partial |
| GitHub API failure | Career analyzer raises error; local path works | Remote repo analysis fails | Cache last repo data and show retry | Partial |
| Browser automation failure | Action status can record failures | Partial plan may remain | Retry per action and clearer UI state | Partial |
| Network failure | Local UI remains usable | OAuth/GitHub/Gmail fail | Offline mode messaging | Partial |
| Gmail OAuth missing/API disabled | Connector records setup-required status | Gmail import unavailable | Enable API or local mbox import | Pass |

## Phase 8 - Agent Failure Testing

| Agent | Failure Probe | Result | Risk |
| --- | --- | --- | --- |
| Planner | Invalid `/api/planner` payload | 400 `goal is required` | Low |
| Memory | Invalid entity/fact payloads | 400 validation errors | Low |
| Career | Invalid repo/job/resume via UI while unlocked path previously tested | Error route path handled, but exact UX should be rechecked unlocked | Medium |
| Browser Agent | Unknown connector and invalid plans not fully executed | Browser plan failures covered by unit tests, not full browser crash | Medium |
| Desktop Automation | Unit tests cover safety; no live destructive test run | Residual OS-specific risk | High |

Failure Isolation Report:

- Agent packages use separate SQLite DBs and service wrappers, which helps isolation.
- Import-time failure in one Flask service may still break route rendering for that page.
- Background worker failures are not yet surfaced strongly on the main dashboard.

## Phase 9 - Security Audit

Security probes:

- Locked API without session: 401.
- Locked UI route: redirects to login.
- Bad browser `Origin`: 403.
- Trusted origin while locked: 401.
- Dependency audit already passed.
- Secret scan over new Career files and docs found no private token values.

Security Findings:

| ID | Severity | Finding | Impact | Reproduction | Fix Recommendation |
| --- | --- | --- | --- | --- | --- |
| SEC-1 | High | `/api/local/pairing` returns `api_token` to any loopback caller when `LOCAL_API_TOKEN` is set. | Any local process/browser page that can reach loopback may retrieve the trusted API token. | `GET /api/local/pairing` from loopback. | Require unlocked session or one-time pairing approval; never return token on a simple GET. |
| SEC-2 | Medium | `/api/wellbeing/activity` accepts empty JSON and creates an activity record. | Local clients can pollute activity data. | POST `{}` returned 201. | Require at least app name/category/duration or token-authenticated trusted client. |
| SEC-3 | Medium | Memory write path calls Ollama per fact with timeout. | Local prompt/content can trigger repeated slow local requests and resource exhaustion. | 100/1000 memory stress timed out. | Add async embedding queue, circuit breaker, and offline skip. |
| SEC-4 | Low | Desktop launcher prints local data path and URL. | Low data exposure in console/logs. | Static scan. | Keep for dev, suppress in production unless debug enabled. |
| SEC-5 | Low | `innerHTML` used in live dashboard rendering. | Current dynamic values are escaped, but future renderer changes could introduce XSS. | Static scan. | Prefer DOM construction or enforce trusted escaping helpers. |

## Phase 10 - Performance Testing

Already completed:

- Full test suite passed.
- Packaged `/career` route returned 200.

New performance probes:

| Test | Result | Status |
| --- | --- | --- |
| Empty DB `/career` first load | 523.7 ms | Acceptable but watch |
| Empty DB `/api/live` | 2.4 ms | Pass |
| Career 500 applications insert | 11,738.7 ms | Slow write path |
| Career dashboard with 500 applications | 17.4 ms | Pass |
| 1000 memory insert stress | Timed out after 184 seconds | Fail |
| 100 memory insert stress | Timed out after 124 seconds | Fail |

Performance Benchmark Report:

- Cold and warm native app start were not retested because packaged launch was already verified.
- Memory write stress is a release blocker. The embedding path attempts network calls per memory item with an 8-second timeout. This must move off the synchronous request path.
- Career application writes should be batched for import scenarios.

## Phase 11 - Responsive UI Testing

Viewport matrix:

- Mobile: 390x844
- Tablet: 768x1024
- Laptop: 1366x768
- Ultrawide: 1920x1080

Pages:

- `/`
- `/mobile`
- `/automation`
- `/browser-agent`
- `/career`
- `/connectors`
- `/memory`
- `/planner`

Results:

- No horizontal overflow.
- No detected clipped button/card/form text.
- No console errors.
- Vertical strip bug not reproduced.

Residual risk:

- 4K and native PyWebView DPI scaling were not visually captured in this pass.

## Phase 12 - Accessibility Review

Automated static checks:

| Check | Result |
| --- | --- |
| H1 present on sampled pages | Pass |
| Buttons/links have accessible text | Pass |
| Inputs have label/placeholder/aria-label | 2 failures |
| Console errors during responsive checks | Pass |

Accessibility Findings:

- Planner cadence select needs a label.
- Sources file input needs a label.
- Need full keyboard-only test for menu, forms, and status updates.
- Need color contrast audit for muted gray-on-dark and neon labels.

## Phase 13 - Pre-Release Checklist

| Checklist Item | Status | Notes |
| --- | --- | --- |
| No placeholder components | Warning | Career seeds placeholder projects intentionally; acceptable for MVP but should be marked as onboarding. |
| No debug logs | Warning | Console/print messages exist in desktop launcher and notifications. |
| No test data | Warning | Real local DB contains prior QA-created Career analysis and app data. Release package should not ship data. |
| No dead routes | Pass | Safe GET route sweep passed. |
| No unused API calls | Warning | Not fully proven; app.js uses known live endpoints. |
| No unused database tables | Warning | Not fully proven; agent DBs have forward-looking tables. |
| No broken links | Pass | Rendered links did not break in smoke routes. |
| No unhandled exceptions | Warning | Stress tests timed out; DB failure mode not fully isolated. |
| No missing assets | Pass | Existing screenshot/icon assets referenced by README and templates exist. |
| No TODOs in production code | Pass | Static scan did not find TODO/FIXME in app/agent code. |

## Phase 14 - Release Blockers

### Critical Issues

None confirmed.

### High Issues

| ID | Description | Impact | Reproduction Steps | Fix Recommendation |
| --- | --- | --- | --- | --- |
| HIGH-1 | Memory write stress fails because each `remember()` calls Ollama embedding synchronously. | Large imports or first sync can hang for minutes. | Insert 100 or 1000 memory facts with Ollama unavailable/slow. | Add embedding circuit breaker, async queue, bulk import mode, and a config flag to skip embeddings when offline. |
| HIGH-2 | Local pairing endpoint can expose `LOCAL_API_TOKEN`. | Local malicious process or browser context could obtain trusted API token. | Configure `LOCAL_API_TOKEN`, request `/api/local/pairing` from loopback. | Require unlocked session or explicit one-time pairing confirmation and avoid returning persistent token. |

### Medium Issues

| ID | Description | Impact | Reproduction Steps | Fix Recommendation |
| --- | --- | --- | --- | --- |
| MED-1 | `/api/wellbeing/activity` accepts empty payloads. | Polluted activity metrics and misleading wellbeing dashboard. | POST `{}` to `/api/wellbeing/activity`; got 201. | Validate required signal fields and auth expected clients. |
| MED-2 | Accessibility label gaps in Planner and Sources. | Screen reader and keyboard users lose context. | Static form scan. | Add labels/ARIA. |
| MED-3 | GitHub API failure does not use cached Career repository data. | Remote analysis is brittle when offline/rate-limited. | Force invalid remote/API failure. | Use last successful analysis and show stale-data warning. |
| MED-4 | Background worker failure state is not prominent on main dashboard. | User may assume live syncing is active when worker failed. | Stop worker or fail dependency. | Promote worker health to dashboard warning. |

### Low Issues

| ID | Description | Impact | Fix Recommendation |
| --- | --- | --- | --- |
| LOW-1 | Desktop launcher prints local path and URL. | Low information disclosure in logs. | Suppress unless debug mode. |
| LOW-2 | Career application import write path is slow for bulk import. | Imports may feel sluggish. | Add bulk `executemany` or transaction batching. |
| LOW-3 | First-run empty states can be more instructive. | User onboarding friction. | Add actionable setup cards. |

## Complete Fix Plan

1. **Fix HIGH-1:** make memory embeddings asynchronous and add an Ollama circuit breaker.
2. **Fix HIGH-2:** redesign `/api/local/pairing` as an unlocked, one-time pairing flow.
3. **Fix MED-1:** validate wellbeing activity payloads and require useful signal fields.
4. **Fix MED-2:** add missing form labels and run keyboard-only smoke test.
5. **Fix MED-3:** cache Career GitHub analyses and use stale data on API failure.
6. **Fix MED-4:** add worker health warnings to the main dashboard.
7. Add repeatable benchmark scripts for 1000 memories, 100 projects, 500 applications, and 100 browser tasks.
8. Add Playwright E2E tests for all primary forms and navigation.
9. Add native PyWebView visual pass at 100, 125, 150 percent Windows scaling.
10. Re-run this QA audit and require score >= 85 before release.
