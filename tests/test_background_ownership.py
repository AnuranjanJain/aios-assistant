from hackathon_monitor_worker import scan_once
from app.services import background_services
from desktop_app import PollingWorker
import threading
import time


def test_opportunity_worker_does_not_claim_gmail(monkeypatch):
    seen = []

    def fake_run_connector(connector_id, *args, **kwargs):
        seen.append(connector_id)
        return type("Result", (), {"connector_id": connector_id, "message": "ok"})()

    monkeypatch.setattr("hackathon_monitor_worker.run_connector", fake_run_connector)
    monkeypatch.setattr("hackathon_monitor_worker.create_app", lambda: None)
    monkeypatch.setattr("hackathon_monitor_worker.get_effective_config", lambda _config: {
        "AI_PROVIDER": "rule_based",
        "OLLAMA_URL": "http://127.0.0.1:11434",
        "OLLAMA_MODEL": "local",
    })
    monkeypatch.setattr("hackathon_monitor_worker.db", type("Db", (), {
        "session": type("Session", (), {"commit": lambda _self: None})(),
    })())

    class FakeContext:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeApp:
        config = {}

        def app_context(self):
            return FakeContext()

    scan_once(FakeApp())
    assert seen == ["hackathon_platforms", "job_portals"]


def test_polling_worker_backs_off_after_transient_failure(monkeypatch):
    background_services._services.clear()
    background_services.register_service("test", "Test", "Test worker")
    calls = []
    stop = threading.Event()

    def callback(_state):
        calls.append(time.monotonic())
        if len(calls) == 2:
            stop.set()
        raise RuntimeError("temporary Gmail outage")

    worker = PollingWorker("test", callback, {}, lambda _state: None, interval=0.01)
    monkeypatch.setattr(worker, "stop_event", stop)
    worker.start()
    worker.join(timeout=1)

    status = background_services.list_background_services()[0]
    assert len(calls) == 2
    assert calls[1] - calls[0] >= 0.015
    assert status["failure_count"] == 2
    assert status["last_error"] == "temporary Gmail outage"
    assert status["next_run_at"] is not None
    background_services._services.clear()
