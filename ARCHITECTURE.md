# AiOS Assistant Architecture

This document explains how AiOS Assistant should work as both a standalone app and a plugin-powered local AI agent.

## Product Shape

AiOS Assistant has one local agent core and multiple user-facing surfaces.

```text
                         Smartphone / PWA
                               |
Browser plugin  ---->  Local Flask API  <----  Web dashboard
                               |
                       Agent services layer
                               |
              SQLite/PostgreSQL + background scheduler
                               |
                         Ollama local LLM
```

The local backend is the source of truth. It owns the database, AI classification, reminders, planning logic, and integration rules.

The web app, plugin, and phone UI are clients. They should send data to the backend and display results from it.

## Main Components

### 1. Local Backend

Current stack:

- Flask
- Flask-SQLAlchemy
- SQLite

Future stack:

- Flask or FastAPI
- PostgreSQL for long-term storage
- APScheduler or Celery for background jobs
- Redis if queued jobs become necessary

Responsibilities:

- receive inputs
- call the local AI model
- store structured memory
- create reminders
- generate daily plans
- expose API endpoints for app/plugin clients

### 2. Local AI Brain

Recommended local runtime:

- Ollama

The backend talks to Ollama over:

```text
http://localhost:11434
```

The AI should return structured JSON, not casual text.

Example output:

```json
{
  "category": "job",
  "status": "Interview Scheduled",
  "title": "Backend Intern interview",
  "organization": "Example Company",
  "deadline": "2026-06-04T15:00:00",
  "action_needed": "Prepare backend and system design notes",
  "confidence": 0.88
}
```

### 3. Web Dashboard

The dashboard is the full app experience.

It should support:

- daily plan
- tracked jobs
- tracked hackathons
- reminders
- recent inbox intelligence
- wellbeing insights
- settings
- plugin connection status

### 4. Browser Plugin

The plugin is a capture layer.

It should be able to:

- capture selected text
- capture job pages
- capture hackathon pages
- capture Gmail thread details when permitted
- send page context to the local backend
- show a small popup summary

The plugin should call local endpoints such as:

```text
POST http://localhost:5000/api/track-job
POST http://localhost:5000/api/track-hackathon
POST http://localhost:5000/api/ingest-email
POST http://localhost:5000/api/wellbeing/activity
GET  http://localhost:5000/api/today
```

Current MVP files:

```text
extension/
  manifest.json
  popup.html
  popup.css
  popup.js
  content.js
```

The popup has four actions:

- Save Page
- Track Job
- Track Hackathon
- Log Activity

The content script reads:

- page title
- primary heading
- selected text
- meta description
- URL
- hostname

Then the popup posts that context to the local Flask API.

### 5. Smartphone / PWA

The phone should use the laptop as the AI server.

```text
Phone browser
        |
http://LAPTOP-IP:5000
        |
Flask backend on laptop
        |
Ollama on laptop
```

This lets the phone access the assistant without running a model locally.

Before exposing the app on LAN, add authentication.

Current mobile route:

```text
GET /mobile
```

PWA files:

```text
app/static/manifest.webmanifest
app/static/service-worker.js
app/static/app.js
app/static/icons/aios-icon.svg
```

The PWA starts on `/mobile` and can be installed from supported mobile browsers.

### 6. Desktop App

The desktop app is a local wrapper around the same Flask backend.

```text
desktop_app.py
        |
starts Flask on 127.0.0.1:5050
        |
opens native pywebview window
        |
falls back to system browser when webview is unavailable
        |
starts reminder worker thread
```

Packaging starter:

```text
desktop_app.spec
```

## Real-Time Layer

Current live behavior:

- browser UI polls `GET /api/live` every 15 seconds
- dashboard/mobile stats update without a full page refresh
- `local_worker.py` checks reminders every 30 seconds
- `desktop_app.py` starts the reminder worker automatically
- desktop notifications use `plyer` when available and terminal output as a fallback
- reminders are marked read after notification so the same reminder is not repeatedly sent

Reminder state:

- `is_read`: user has seen it, so workers should not notify again.
- `is_done`: task is complete.
- `notified_at`: when the desktop worker or reminder connector last notified.

Live endpoint:

```text
GET /api/live
```

Returns:

- current plan
- dashboard stats
- latest opportunity
- latest wellbeing activity
- top reminders
- update timestamp

## Data Flow

### Real Data Sources

Current real input sources:

```text
Browser extension
Local file import
Watch folder import
Desktop activity worker
Manual dashboard/mobile capture
Connector registry
```

Near-future real input sources:

```text
Gmail OAuth
Google Calendar
Android wellbeing export
Local filesystem watch folders
```

### Email Flow

```text
Gmail/local email/manual paste/file import
        |
Backend ingest endpoint
        |
Local AI classifier
        |
InboxItem saved
        |
Opportunity and Reminder created when useful
        |
Dashboard and daily plan update
```

### Local Import Flow

```text
.eml / .mbox / .json / .csv
        |
/sources/import
        |
data_pipelines.py parser
        |
agent_ingest.py
        |
local AI classifier
        |
InboxItem + Opportunity + Reminder + AgentDecision
```

### Watch Folder Flow

```text
watch_import_worker.py
        |
WATCH_IMPORT_DIR
        |
.eml / .mbox / .json / .csv
        |
data_pipelines.py parser
        |
agent_ingest.py
        |
live dashboard
```

The desktop wrapper starts this worker automatically. Browser mode can run it separately.

### Settings Flow

```text
/settings
        |
Setting table
        |
get_effective_config()
        |
connectors + classifier + watch worker
```

### Local Auth Flow

```text
/login
        |
PIN hash in Setting table
        |
Flask session unlock
        |
dashboard + mobile + API access
```

The PIN lock is local-session protection. Before public exposure, add per-client API tokens and HTTPS.

### Connector Flow

```text
/connectors or /api/connectors/<id>/run
        |
connectors.py registry
        |
source-specific connector
        |
agent_ingest.py or notification service
        |
ConnectorRun history
```

Current connectors:

- Gmail connector: local Gmail Takeout `.mbox` import now, OAuth credential paths prepared.
- Reminder connector: checks reminders and triggers local notifications.
- Job portal connector: imports saved `.json` and `.csv` exports, plus extension live capture.

### Desktop Activity Flow

```text
desktop_activity_worker.py
        |
active window title
        |
category heuristic
        |
ActivityEvent
        |
dashboard/mobile live update
```

### Job Page Flow

```text
User opens job page
        |
Plugin captures title, company, deadline, URL, selected notes
        |
Plugin sends data to backend
        |
AI extracts role/status/action
        |
Opportunity saved
        |
Follow-up reminder created
```

### Hackathon Flow

```text
User opens Devfolio/Unstop/hackathon page
        |
Plugin sends context to backend
        |
AI extracts event name, team info, phases, deadline
        |
Hackathon opportunity saved
        |
Timeline generated:
- idea
- prototype
- pitch deck
- demo
- submission
```

### Digital Wellbeing Flow: "What Do You Do"

The Digital Wellbeing integration should compare planned work with actual behavior.

```text
Daily plan
        |
User activity signal
        |
Wellbeing analyzer
        |
Mismatch detection
        |
Plan adjustment or reminder
```

Example:

```text
Planned:
- 90 min interview prep
- 45 min DSA

Observed:
- 50 min social media
- 10 min coding

Agent action:
- mark focus drift
- suggest a 25 min recovery block
- move DSA later
- show a short reminder
```

Possible activity sources:

- browser plugin reports active site category
- Android Digital Wellbeing export/manual input
- desktop app usage tracker
- user check-in prompt: "What are you doing right now?"
- calendar/focus timer session

Important privacy rule:

The wellbeing data should stay local by default.

## Memory Model

Useful future tables:

```text
InboxItem
Opportunity
Reminder
ActivityEvent
FocusSession
DailyPlan
AgentDecision
UserPreference
```

`ActivityEvent` can store:

- source
- app/site/category
- started_at
- ended_at
- duration_seconds
- planned_task
- actual_task
- agent_summary

`AgentDecision` can store:

- input type
- model used
- decision JSON
- confidence
- created reminders
- created opportunities

## Local-First Security

Rules:

- Keep AI inference local by default.
- Do not expose Flask publicly without authentication.
- Do not store raw email bodies longer than needed unless the user enables it.
- Keep OAuth secrets in `.env`.
- Use LAN access only for trusted devices.
- Add auth before phone/PWA usage.

## Build Order

1. Add Ollama classifier. Done in initial phase.
2. Add stable JSON schema for AI outputs. Done in initial phase.
3. Add local API endpoints. Started in initial phase.
4. Add Digital Wellbeing activity tables. Started in initial phase.
5. Add plugin MVP.
6. Add phone/PWA support.
7. Add auth.
8. Add Gmail import.
9. Add Calendar integration.
10. Add optional Telegram notifications.

## Initial Build Phase Status

Implemented:

- `AI_PROVIDER=ollama` support with rule-based fallback
- structured classification fields
- `AgentDecision` storage
- `ActivityEvent` storage
- `POST /api/ingest-email`
- `POST /api/track-job`
- `POST /api/track-hackathon`
- `POST /api/wellbeing/activity`
- `GET /api/today`
- `GET /api/opportunities`
- Digital Wellbeing panel on the dashboard
- browser extension MVP for page/job/hackathon/wellbeing capture
- PWA manifest and service worker
- phone-first `/mobile` dashboard
- desktop webview launcher
- live dashboard polling
- local reminder worker
- desktop notification foundation
- local import pipeline for `.eml`, `.mbox`, `.json`, `.csv`
- desktop activity worker for real wellbeing data

Next:

- improve the browser plugin with context menus and richer Gmail/job-page extraction
- add authentication before LAN/mobile use
- add a real migration workflow before the database schema becomes larger
