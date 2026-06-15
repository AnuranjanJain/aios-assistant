import json
import os
import time
from pathlib import Path

from app import create_app
from app.models import db
from app.services.ai_classifier import get_classifier
from app.services.data_pipelines import SUPPORTED_IMPORTS, import_source_file
from app.services.settings import get_effective_config


STATE_PATH = Path(os.getenv("AIOS_WATCH_STATE_PATH", ".aios_watch_state.json"))
CHECK_INTERVAL_SECONDS = 20


def load_state():
    if not STATE_PATH.exists():
        return {"processed": []}

    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"processed": []}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def file_key(path):
    stat = path.stat()
    return f"{path.resolve()}::{stat.st_size}::{int(stat.st_mtime)}"


def scan_once(app, state):
    processed = set(state.get("processed", []))

    with app.app_context():
        values = get_effective_config(app.config)
        watch_dir = Path(values.get("WATCH_IMPORT_DIR") or "imports/watch")
        watch_dir.mkdir(parents=True, exist_ok=True)

        classifier = get_classifier(values["AI_PROVIDER"], values["OLLAMA_URL"], values["OLLAMA_MODEL"])
        imported_count = 0

        for path in sorted(watch_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_IMPORTS:
                continue

            key = file_key(path)
            if key in processed:
                continue

            imported = import_source_file(
                path,
                classifier=classifier,
                provider=values["AI_PROVIDER"],
                model=values["OLLAMA_MODEL"],
                limit=100,
            )
            imported_count += len(imported)
            processed.add(key)

        if imported_count:
            db.session.commit()
            print(f"Imported {imported_count} records from watch folder.")

    state["processed"] = sorted(processed)
    return imported_count


def main():
    app = create_app()
    state = load_state()
    print("AiOS watch import worker is running. Press Ctrl+C to stop.")

    while True:
        scan_once(app, state)
        save_state(state)
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
