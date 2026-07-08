from urllib.parse import urlsplit

from app.models import ConnectedAccount, PlanningEvent
from app.services.background_services import list_background_services


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _is_loopback_url(value):
    parsed = urlsplit(value or "")
    return parsed.hostname in LOOPBACK_HOSTS


def _service_status(service_id):
    for service in list_background_services():
        if service.get("id") == service_id:
            return service
    return None


def readiness_summary(values):
    accounts = ConnectedAccount.query.order_by(ConnectedAccount.created_at.desc()).all()
    enabled_accounts = [account for account in accounts if account.sync_enabled]
    planner_count = PlanningEvent.query.count()
    questions_waiting = PlanningEvent.query.filter(
        PlanningEvent.next_question.isnot(None),
        PlanningEvent.status.notin_(["done", "cancelled"]),
    ).count()
    email_worker = _service_status("email_intelligence")
    ollama_url = values.get("OLLAMA_URL") or "http://localhost:11434"
    sync_interval = values.get("EMAIL_SYNC_INTERVAL_MINUTES") or "10"

    items = [
        {
            "id": "privacy",
            "label": "Local-only privacy",
            "ok": _is_loopback_url(ollama_url),
            "detail": "Ollama and client APIs stay on loopback. Email content is not sent to cloud AI.",
            "action": (
                "Keep OLLAMA_URL on http://localhost:11434 or another loopback address."
                if _is_loopback_url(ollama_url)
                else "Change OLLAMA_URL back to http://localhost:11434 before syncing private data."
            ),
        },
        {
            "id": "gmail_account",
            "label": "Gmail account",
            "ok": bool(accounts),
            "detail": (
                f"{len(accounts)} account connected, {len(enabled_accounts)} syncing"
                if accounts
                else "Connect at least one Google account for email planning."
            ),
            "action": (
                "Use AiOS Settings -> Connected Google accounts to add, rename, pause, or sync accounts."
                if accounts
                else "Add a Google OAuth client file, then connect your first Gmail account in AiOS Settings."
            ),
        },
        {
            "id": "gmail_sync",
            "label": "Gmail sync",
            "ok": bool(enabled_accounts),
            "detail": f"Background sync interval: {sync_interval} minutes.",
            "action": (
                "Use Sync All Now after connecting accounts, or leave the desktop app open for background sync."
                if enabled_accounts
                else "Enable sync for at least one connected Gmail account."
            ),
        },
        {
            "id": "email_worker",
            "label": "Email worker",
            "ok": bool(email_worker and email_worker.get("running")),
            "detail": (
                "Worker is running in the desktop app."
                if email_worker and email_worker.get("running")
                else "Starts automatically when the installed desktop app is open."
            ),
            "action": (
                "Keep AiOS running in tray so new email can become planner rows."
                if email_worker and email_worker.get("running")
                else "Open the installed AiOS desktop app, or enable startup from Settings."
            ),
        },
        {
            "id": "ollama",
            "label": "Ollama loopback",
            "ok": _is_loopback_url(ollama_url),
            "detail": f"{ollama_url} using {values.get('OLLAMA_MODEL') or 'selected local model'}.",
            "action": "For a 4GB RTX 3050, run: ollama pull qwen2.5:3b, then Test Ollama in AiOS Settings.",
        },
        {
            "id": "github",
            "label": "GitHub repo tracking",
            "ok": bool(values.get("GITHUB_TOKEN")),
            "detail": (
                "Token saved for private repos and higher rate limits."
                if values.get("GITHUB_TOKEN")
                else "Optional: add a GitHub token to read private repo activity."
            ),
            "action": (
                "Repo rows will refresh recent commits, open issues, and open PR counts."
                if values.get("GITHUB_TOKEN")
                else "Paste a GitHub token in AiOS Settings if you want private repo activity."
            ),
        },
        {
            "id": "planner",
            "label": "Planner rows",
            "ok": planner_count > 0,
            "detail": (
                f"{planner_count} real-life rows ready, {questions_waiting} waiting for your answer."
                if planner_count
                else "Rows appear after Gmail, hackathon, goal, repo, or manual events are added."
            ),
            "action": (
                "Answer waiting questions in WDYD to keep work done, work left, and notes current."
                if planner_count
                else "Create a manual WDYD row for a hackathon, repo, goal, or learning video to start today."
            ),
        },
    ]

    ready = sum(1 for item in items if item["ok"])
    return {
        "ready": ready,
        "total": len(items),
        "items": items,
        "all_ready": ready == len(items),
    }
