import ctypes
import subprocess
import sys
import time
from datetime import datetime

from app import create_app
from app.models import ActivityEvent, db
from app.services.wellbeing import summarize_activity


CHECK_SECONDS = 10
MIN_LOG_SECONDS = 60


def get_active_window_title():
    if sys.platform != "win32":
        return get_linux_active_window_title()

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip() or "Unknown window"


def get_linux_active_window_title():
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""

    return result.stdout.strip() or "Unknown window"


def categorize_window(title):
    text = title.lower()
    if any(term in text for term in ["visual studio", "vs code", "pycharm", "terminal", "powershell"]):
        return "coding"
    if any(term in text for term in ["youtube", "netflix", "prime video", "hotstar"]):
        return "entertainment"
    if any(term in text for term in ["instagram", "x.com", "twitter", "reddit", "facebook"]):
        return "social"
    if any(term in text for term in ["leetcode", "geeksforgeeks", "hackerrank"]):
        return "dsa"
    if any(term in text for term in ["gmail", "outlook", "mail"]):
        return "email"
    if any(term in text for term in ["docs", "notion", "obsidian", "onenote"]):
        return "study"
    return "unknown"


def log_activity(app, title, started_at, ended_at):
    duration_seconds = int((ended_at - started_at).total_seconds())
    if duration_seconds < MIN_LOG_SECONDS:
        return

    duration_minutes = max(1, round(duration_seconds / 60))
    category = categorize_window(title)
    summary = summarize_activity(category, duration_minutes, actual_task=title)

    with app.app_context():
        db.session.add(
            ActivityEvent(
                source="desktop activity worker",
                app_name=title[:120],
                category=category,
                actual_task=title[:180],
                duration_minutes=duration_minutes,
                started_at=started_at,
                ended_at=ended_at,
                agent_summary=summary,
            )
        )
        db.session.commit()


def scan_once(app, state):
    current_title = state.get("current_title") or get_active_window_title()
    if not current_title:
        return

    started_at = state.get("started_at") or datetime.utcnow().isoformat()
    next_title = get_active_window_title()
    if not next_title or next_title == current_title:
        state["current_title"] = current_title
        state["started_at"] = started_at
        return

    ended_at = datetime.utcnow()
    try:
        started_at_dt = datetime.fromisoformat(started_at)
    except ValueError:
        started_at_dt = ended_at
    log_activity(app, current_title, started_at_dt, ended_at)
    state["current_title"] = next_title
    state["started_at"] = ended_at.isoformat()


def main():
    app = create_app()
    current_title = get_active_window_title()
    started_at = datetime.utcnow()
    print("AiOS desktop activity worker is running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(CHECK_SECONDS)
            next_title = get_active_window_title()
            if next_title == current_title:
                continue

            ended_at = datetime.utcnow()
            log_activity(app, current_title, started_at, ended_at)
            current_title = next_title
            started_at = ended_at
    except KeyboardInterrupt:
        log_activity(app, current_title, started_at, datetime.utcnow())


if __name__ == "__main__":
    main()
