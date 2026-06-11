import time

from app import create_app
from app.models import db
from app.services.ai_classifier import get_classifier
from app.services.connectors import run_connector
from app.services.settings import get_effective_config


def scan_once(app):
    with app.app_context():
        values = get_effective_config(app.config)
        classifier = get_classifier(values["AI_PROVIDER"], values["OLLAMA_URL"], values["OLLAMA_MODEL"])
        results = []

        for connector_id in ("gmail", "hackathon_platforms"):
            result = run_connector(
                connector_id,
                values,
                classifier=classifier,
                provider=values["AI_PROVIDER"],
                model=values["OLLAMA_MODEL"],
            )
            results.append(result)

        db.session.commit()
        return results


def main():
    app = create_app()
    print("AiOS hackathon monitor is running. Press Ctrl+C to stop.")

    while True:
        with app.app_context():
            values = get_effective_config(app.config)
            interval_minutes = max(1, int(values.get("HACKATHON_SCAN_INTERVAL_MINUTES") or 5))

        for result in scan_once(app):
            print(f"{result.connector_id}: {result.message}")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    main()
