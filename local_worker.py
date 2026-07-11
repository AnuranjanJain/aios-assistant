import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from app import create_app
from app.services.notifications import notification_center


STATE_PATH = Path(os.getenv("AIOS_WORKER_STATE_PATH", ".aios_worker_state.json"))
CHECK_INTERVAL_SECONDS = 30
REMINDER_LOOKAHEAD_MINUTES = 10


def load_state():
    if not STATE_PATH.exists():
        return {"notified_reminders": []}

    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"notified_reminders": []}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def check_reminders(app, state):
    now = datetime.utcnow()

    with app.app_context():
        state["last_result"] = notification_center(now + timedelta(minutes=REMINDER_LOOKAHEAD_MINUTES), send=True)


def main():
    app = create_app()
    state = load_state()
    print("AiOS local worker is running. Press Ctrl+C to stop.")

    while True:
        check_reminders(app, state)
        save_state(state)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
