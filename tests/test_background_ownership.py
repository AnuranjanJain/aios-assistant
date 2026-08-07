from hackathon_monitor_worker import scan_once


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
