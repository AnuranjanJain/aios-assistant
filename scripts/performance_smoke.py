"""Bounded local dashboard benchmark for release evidence.

This uses synthetic metadata only. It measures warm Flask test-client reads
against a 10,000-message SQLite mailbox and never touches the user's data.
"""

from __future__ import annotations

import json
import argparse
import statistics
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.models import ConnectedAccount, EmailMessage, db


DATASET_SIZE = 10_000
SAMPLES = 15
P95_LIMIT_MS = 1_500.0


def _percentile(values, percentile):
    if len(values) == 1:
        return values[0]
    return statistics.quantiles(values, n=100, method="inclusive")[percentile - 1]


def _measure(client, path, samples):
    client.get(path, headers={"X-AiOS-Token": "performance-smoke-token"})
    values = []
    for _ in range(samples):
        started = time.perf_counter()
        response = client.get(path, headers={"X-AiOS-Token": "performance-smoke-token"})
        elapsed = (time.perf_counter() - started) * 1000
        if response.status_code != 200:
            raise RuntimeError(f"{path} returned HTTP {response.status_code}")
        values.append(elapsed)
    return {
        "samples": len(values),
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": round(_percentile(values, 95), 2),
        "max_ms": round(max(values), 2),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a synthetic local AiOS dashboard benchmark.")
    parser.add_argument("--dataset-size", type=int, default=DATASET_SIZE)
    parser.add_argument("--samples", type=int, default=SAMPLES)
    parser.add_argument("--p95-limit-ms", type=float, default=P95_LIMIT_MS)
    args = parser.parse_args(argv)
    if args.dataset_size < 1 or args.samples < 2:
        parser.error("dataset size must be positive and samples must be at least 2")

    with tempfile.TemporaryDirectory(prefix="aios-performance-") as directory:
        database = Path(directory) / "performance.db"

        class BenchmarkConfig:
            TESTING = True
            SECRET_KEY = "performance-smoke-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database.as_posix()}"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            LOCAL_API_TOKEN = "performance-smoke-token"
            AI_PROVIDER = "rule_based"
            OLLAMA_URL = "http://127.0.0.1:9"
            MEMORY_VECTOR_BACKEND = "sqlite"
            MEMORY_VECTOR_PATH = str(Path(directory) / "vectors")
            USER_DISPLAY_NAME = "Synthetic Benchmark"

        app = create_app(BenchmarkConfig)
        with app.app_context():
            account = ConnectedAccount(provider="google", email="benchmark@example.test", label="Synthetic")
            db.session.add(account)
            db.session.flush()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            records = [
                EmailMessage(
                    account_id=account.id,
                    provider_message_id=f"benchmark-{index}",
                    provider_thread_id=f"thread-{index}",
                    sender="sender@example.test",
                    subject=f"Synthetic message {index}",
                    snippet="Synthetic benchmark content.",
                    body_text="Synthetic benchmark content only.",
                    labels_json="[]",
                    is_unread=index % 7 == 0,
                    sent_at=now - timedelta(minutes=index),
                )
                for index in range(args.dataset_size)
            ]
            db.session.bulk_save_objects(records)
            db.session.commit()

        with app.app_context():
            engine = db.engine
            with app.test_client() as client:
                measurements = {
                    "/api/live": _measure(client, "/api/live", args.samples),
                    "/api/inbox/overview": _measure(client, "/api/inbox/overview", args.samples),
                }
            db.session.remove()
            engine.dispose()

    passed = all(item["p95_ms"] <= args.p95_limit_ms for item in measurements.values())
    payload = {
        "ok": passed,
        "synthetic": True,
        "dataset_messages": args.dataset_size,
        "samples_per_route": args.samples,
        "p95_limit_ms": args.p95_limit_ms,
        "routes": measurements,
    }
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
