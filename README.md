# AiOS Assistant

AiOS Assistant is a local-first AI productivity agent. The goal is to make it work both as a normal standalone web app and as a lightweight plugin/extension that can send useful context into the same local agent brain.

It is designed to become a personal executive assistant for:

- Email intelligence
- Job application tracking
- Hackathon tracking
- Smart reminders
- Daily planning
- Calendar-ready scheduling
- Digital wellbeing and focus tracking

## MVP Features

- Classifies incoming email-like messages into jobs, hackathons, interviews, rejections, deadlines, and general updates.
- Stores tracked opportunities in SQLite.
- Generates daily summaries and simple schedule recommendations.
- Exposes a clean Flask dashboard.
- Includes integration placeholders for Gmail, Google Calendar, Telegram, local AI, and plugin clients.

## Vision

AiOS Assistant should have one shared local backend and multiple surfaces:

```text
Ollama / local model
        ^
Flask agent backend
        ^
SQLite / PostgreSQL + scheduler
        ^
Local API endpoints
   /                  \
Web dashboard      Browser/mobile/plugin clients
```

The separate web app is the main dashboard. It shows tracked jobs, hackathons, reminders, plans, and recent AI decisions.

The plugin is a companion layer. It should capture useful context from places like Gmail, LinkedIn, Unstop, Devfolio, job pages, or a Digital Wellbeing-style app, then send that context to the local backend.

The plugin should stay thin. It should not contain the whole AI system. The AI logic, memory, database, and planner live in the local backend.

## Local-First AI

The preferred workflow is fully local for AI reasoning:

```text
Email / page / wellbeing signal
        |
Local Flask backend
        |
Ollama model on this machine
        |
Structured result saved to database
        |
Dashboard, reminders, and daily plan update
```

This avoids sending private emails, schedules, habits, and productivity data to cloud AI providers.

Recommended local model runner:

- Ollama

Recommended starter models:

- `qwen2.5:7b`
- `llama3.1:8b`
- `mistral:7b`
- `phi3:mini` for lighter machines

Cloud models can still be optional later, but local AI should be the default.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
flask --app app run --debug
```

Open:

```text
http://127.0.0.1:5000
```

Mobile dashboard:

```text
http://127.0.0.1:5000/mobile
```

If using Ollama locally, make sure Ollama is running:

```text
http://localhost:11434
```

Later, set:

```env
AI_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b
```

Pull the model once:

```powershell
ollama pull qwen2.5:7b
```

If Ollama is not running or the model is not available, the app falls back to the built-in rule-based classifier so the dashboard and APIs still work.

## Smartphone Access

The phone does not need to run the AI model. The laptop or PC runs Flask and Ollama, and the phone opens the dashboard over the same Wi-Fi.

```text
Phone browser
        |
http://LAPTOP-IP:5000
        |
Flask app on laptop
        |
Ollama on laptop
```

To support this, run Flask on all network interfaces:

```env
HOST=0.0.0.0
PORT=5000
```

Then open this on the phone:

```text
http://YOUR-LAPTOP-IP:5000/mobile
```

The mobile dashboard is PWA-ready. In Chrome on Android, open the mobile URL, open the browser menu, and choose Add to Home screen or Install app.

## Desktop App

The desktop launcher starts the Flask backend on a desktop-only port and opens AiOS Assistant in a native window when `pywebview` is installed.

```powershell
python desktop_app.py
```

The desktop launcher also starts the local reminder worker, so due reminders can trigger desktop notifications while the app is open.

If the native webview is unavailable, it falls back to opening:

```text
http://127.0.0.1:5050
```

## Real-Time Local Mode

The dashboard and mobile dashboard poll the local backend every 15 seconds through:

```text
GET /api/live
```

This keeps key stats and the daily plan fresh without manually refreshing the page.

Run the reminder worker separately when using the browser-based app:

```powershell
python local_worker.py
```

The worker checks every 30 seconds for reminders due in the next 10 minutes. It sends a desktop notification when possible and falls back to terminal output.

Reminder states:

- Read: stop future notifications for that reminder, but keep the reminder visible.
- Done: complete the reminder and also mark it read.

For the all-in-one desktop experience, use:

```powershell
python desktop_app.py
```

Track real desktop activity:

```powershell
python desktop_activity_worker.py
```

This watches the active window title locally and logs Digital Wellbeing events when you spend at least 60 seconds in a window.

Auto-import real files from a watch folder:

```powershell
python watch_import_worker.py
```

By default it watches `imports/watch`. Drop `.eml`, `.mbox`, `.json`, or `.csv` files there and AiOS imports each file once.

Packaging starter:

```powershell
pip install pyinstaller
pyinstaller desktop_app.spec
```

## Project Structure

```text
app/
  __init__.py
  models.py
  routes.py
  services/
    ai_classifier.py
    daily_planner.py
    reminder_engine.py
    integrations.py
  templates/
    dashboard.html
  static/
    styles.css
config.py
run.py
desktop_app.py
desktop_app.spec
watch_import_worker.py
requirements.txt
.env.example
ARCHITECTURE.md
extension/
  manifest.json
  popup.html
  popup.css
  popup.js
  content.js
```

## Core Workflow

```text
1. Input arrives
   - Gmail email
   - manually pasted email
   - job page from plugin
   - hackathon page from plugin
   - calendar event
   - Digital Wellbeing activity signal

2. Local agent classifies the input
   - job application
   - interview
   - rejection
   - hackathon
   - deadline
   - distraction/focus signal
   - general reminder

3. Database is updated
   - inbox item
   - opportunity
   - reminder
   - wellbeing event

4. Planner generates actions
   - follow up after 7 days
   - prepare for interview
   - schedule DSA block
   - reduce distracting app time
   - protect project/deep-work time

5. User sees output
   - dashboard
   - local notification
   - Telegram message, optional
   - mobile/PWA view
```

## Real Data Pipelines

The app should not depend on fake seed data. Current real-data inputs are:

- Browser extension: captures real web pages, selected text, job pages, hackathons, and activity signals.
- Local import page: imports `.eml`, `.mbox`, `.json`, and `.csv` files.
- Watch folder worker: imports real files dropped into `imports/watch`.
- Desktop activity worker: records active desktop window time into wellbeing events.
- Manual capture: paste an actual email/job/deadline into the dashboard or mobile dashboard.

Open:

```text
http://127.0.0.1:5000/sources
```

Settings:

```text
http://127.0.0.1:5000/settings
```

Use settings to configure the AI provider, Ollama URL/model, Gmail Takeout mbox path, Gmail OAuth paths, job portal import folder, and watch import folder.

Security:

- Open `/settings` to enable a local PIN.
- When enabled, dashboard/mobile/API routes require an unlocked browser session.
- Use the Lock button in the sidebar or mobile page to clear the session.
- Keep API PIN/token hardening on the roadmap before exposing this outside trusted LAN.

Supported import formats:

- `.eml`: one exported email file.
- `.mbox`: mailbox export, such as Google Takeout mail export.
- `.json`: list of objects with `sender`/`from`, `subject`/`title`, and `body`/`content` fields.
- `.csv`: columns like `sender`, `subject`, `body` or `from`, `title`, `notes`.

The import pipeline sends each record through the same local classifier and saves real inbox items, opportunities, reminders, and agent decisions.

Watch-folder flow:

```text
imports/watch/*.csv
        |
watch_import_worker.py
        |
local classifier
        |
database + live dashboard
```

## Connectors

Open:

```text
http://127.0.0.1:5000/connectors
```

Current connectors:

- Gmail: imports real Gmail Takeout `.mbox` when `GMAIL_MBOX_PATH` is set. OAuth credential paths are reserved for the next Gmail API step.
- Local Reminders: checks open reminders and sends desktop notifications.
- Job Portals: imports `.json` or `.csv` exports dropped into `imports/job_portals`, and works with the browser extension for live capture.

Connector API:

```text
GET  /api/connectors
POST /api/connectors/gmail/run
POST /api/connectors/reminders/run
POST /api/connectors/job_portals/run
```

Gmail local export setup:

```env
GMAIL_MBOX_PATH=C:\path\to\All mail Including Spam and Trash.mbox
```

Job portal export setup:

```text
imports/job_portals/
  linkedin_jobs.csv
  internshala_saved_jobs.json
```

## Digital Wellbeing App: "What Do You Do"

The Digital Wellbeing connection should answer one main question:

```text
What do you do with your time, and does it match what you planned to do?
```

The wellbeing app or plugin can send activity signals into AiOS Assistant:

- current app or website category
- time spent
- focus session start/end
- distraction spikes
- planned task versus actual task
- user check-in such as "what are you doing right now?"

AiOS Assistant can then compare activity with the daily plan.

Example:

```text
Plan:
- 90 min interview prep
- 60 min project work
- 45 min DSA

Observed:
- 35 min YouTube
- 20 min Instagram
- 15 min VS Code

Agent response:
- You are drifting from the interview-prep block.
- Start a 25 min prep sprint now.
- Move DSA to 9:30 PM.
```

This makes the assistant more than a reminder app. It becomes a feedback loop between intention and actual behavior.

## Plugin Workflow

The plugin should send context to the local backend:

```text
Browser plugin
        |
POST http://localhost:5000/api/ingest
        |
AiOS Assistant backend
        |
Local AI classifier
        |
Database + reminders + planner
```

Example plugin actions:

- Save this job page
- Track this hackathon
- Summarize this Gmail thread
- Create reminder from selected text
- Send current activity to wellbeing tracker

## Browser Extension MVP

The first plugin version lives in:

```text
extension/
```

Load it in Chrome or Edge:

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable Developer mode.
3. Choose Load unpacked.
4. Select the `extension` folder from this project.
5. Keep the Flask app running at `http://127.0.0.1:5000`.

Popup actions:

- Save Page: sends current page title, URL, selected text, and meta description to `/api/ingest-email`.
- Track Job: sends the same page context to `/api/track-job`.
- Track Hackathon: sends the same page context to `/api/track-hackathon`.
- Log Activity: sends the current site and selected activity category to `/api/wellbeing/activity`.

The extension stores only the local API base URL in browser sync storage. The captured page data is sent to your local Flask backend.

## API Direction

Future local API endpoints:

```text
POST /api/ingest-email
POST /api/track-job
POST /api/track-hackathon
POST /api/wellbeing/activity
GET  /api/today
GET  /api/opportunities
```

Current API examples:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:5000/api/ingest-email `
  -ContentType "application/json" `
  -Body '{"sender":"talent@example.com","subject":"Interview schedule for AI Intern","body":"Technical round tomorrow at 4 PM.","source":"manual test"}'
```

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:5000/api/wellbeing/activity `
  -ContentType "application/json" `
  -Body '{"source":"what-do-you-do","app_name":"YouTube","category":"entertainment","duration_minutes":35,"planned_task":"interview prep","actual_task":"watching videos"}'
```

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/today
```

## Roadmap

1. Add Ollama classifier and make local AI the default.
2. Add Gmail import or local email import.
3. Add local API endpoints for plugin clients.
4. Build browser plugin for Gmail/job/hackathon pages.
5. Add Digital Wellbeing activity ingestion.
6. Add mobile/PWA support.
7. Add desktop app wrapper.
8. Add Google Calendar event creation.
9. Add local auth before exposing to phone or LAN.
10. Add optional Telegram notifications.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture.
