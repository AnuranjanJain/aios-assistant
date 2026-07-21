from app.services.workers import WORKERS


def test_aios_workers_do_not_duplicate_wdyd_activity_collection():
    assert "activity" not in WORKERS
    assert set(WORKERS) == {
        "reminders",
        "watch_imports",
        "hackathons",
        "email_intelligence",
    }
