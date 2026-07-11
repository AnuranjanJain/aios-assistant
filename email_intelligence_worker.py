import time

from app import create_app
from app.services.daily_assistant import run_daily_assistant_cycle
from app.services.email_intelligence import run_email_intelligence_cycle
from app.services.settings import get_effective_config


CHECK_INTERVAL_SECONDS = 10 * 60
MIN_INTERVAL_MINUTES = 2


def scan_once(app, state=None):
    with app.app_context():
        result = run_email_intelligence_cycle(get_effective_config(app.config))
        assistant = run_daily_assistant_cycle()
        if state is not None:
            state["last_result"] = result
            state["last_assistant"] = assistant
        return result | {"assistant": assistant}


def sync_interval_seconds(app):
    with app.app_context():
        config = get_effective_config(app.config)
        try:
            minutes = int(config.get("EMAIL_SYNC_INTERVAL_MINUTES") or CHECK_INTERVAL_SECONDS // 60)
        except (TypeError, ValueError):
            minutes = CHECK_INTERVAL_SECONDS // 60
    return max(MIN_INTERVAL_MINUTES, minutes) * 60


def main():
    app = create_app()
    state = {}
    while True:
        scan_once(app, state)
        time.sleep(sync_interval_seconds(app))


if __name__ == "__main__":
    main()
