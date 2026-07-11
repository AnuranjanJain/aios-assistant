import json
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app import create_app
from app.models import (
    ActivityEvent,
    ConnectedAccount,
    EmailMessage,
    GitHubRepository,
    GoalPlan,
    LearningItem,
    MemoryEntity,
    Opportunity,
    PlanningEvent,
    db,
)
from app.services.analytics import analytics_overview, analytics_report


class AnalyticsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "analytics-test.db"

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            LOCAL_API_TOKEN = "local-test-token"
            OLLAMA_URL = "http://127.0.0.1:9"
            OLLAMA_MODEL = "qwen2.5:3b"
            OLLAMA_EMBED_MODEL = "nomic-embed-text"
            MEMORY_VECTOR_BACKEND = "sqlite"
            MEMORY_VECTOR_PATH = str(Path(self.temp_dir.name) / "vectors")
            USER_DISPLAY_NAME = "Anuranjan"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def seed_analytics(self, anchor):
        account = ConnectedAccount(provider="google", email="analytics@example.com")
        goal = MemoryEntity(entity_type="goal", name="Ship AiOS Analytics", slug="ship-aios-analytics")
        db.session.add_all([account, goal])
        db.session.flush()
        db.session.add_all(
            [
                ActivityEvent(
                    source="collector",
                    app_name="VS Code",
                    category="coding",
                    actual_task="Analytics engine",
                    duration_minutes=120,
                    created_at=datetime.combine(anchor, time(10)),
                ),
                ActivityEvent(
                    source="collector",
                    app_name="Browser",
                    category="learning",
                    actual_task="Study workload balance",
                    duration_minutes=60,
                    created_at=datetime.combine(anchor, time(13)),
                ),
                ActivityEvent(
                    source="collector",
                    app_name="VS Code",
                    category="coding",
                    actual_task="Yesterday coding",
                    duration_minutes=45,
                    created_at=datetime.combine(anchor - timedelta(days=1), time(10)),
                ),
                ActivityEvent(
                    source="collector",
                    app_name="VS Code",
                    category="coding",
                    actual_task="Two days ago coding",
                    duration_minutes=45,
                    created_at=datetime.combine(anchor - timedelta(days=2), time(10)),
                ),
            ]
        )
        db.session.add_all(
            [
                Opportunity(kind="hackathon", title="FlightIQ Challenge", updated_at=datetime.combine(anchor, time(9))),
                Opportunity(kind="internship", title="AI Internship", updated_at=datetime.combine(anchor, time(9))),
                EmailMessage(
                    account_id=account.id,
                    provider_message_id="analytics-email-1",
                    subject="Analytics deadline",
                    created_at=datetime.combine(anchor, time(8)),
                ),
                LearningItem(
                    title="Burnout prediction paper",
                    status="in_progress",
                    estimated_minutes=90,
                    updated_at=datetime.combine(anchor, time(12)),
                ),
                PlanningEvent(
                    source_key="analytics:completed",
                    event_type="repo",
                    source="test",
                    title="Finish analytics API",
                    project="AiOS",
                    planned_minutes=90,
                    status="completed",
                    updated_at=datetime.combine(anchor, time(16)),
                ),
                PlanningEvent(
                    source_key="analytics:blocked",
                    event_type="goal",
                    source="test",
                    title="Blocked workload review",
                    project="AiOS",
                    deadline=datetime.combine(anchor - timedelta(days=1), time(18)),
                    planned_minutes=45,
                    status="blocked",
                    updated_at=datetime.combine(anchor, time(17)),
                ),
                GoalPlan(
                    goal_id=goal.id,
                    title="Analytics Goal",
                    cadence="weekly",
                    status="completed",
                    updated_at=datetime.combine(anchor, time(16)),
                ),
                GitHubRepository(
                    repo_full_name="AnuranjanJain/aios-assistant",
                    html_url="https://github.com/AnuranjanJain/aios-assistant",
                    commits_json=json.dumps(
                        [
                            {
                                "sha": "abc123",
                                "message": "add analytics report",
                                "date": datetime.combine(anchor, time(11)).isoformat(),
                            }
                        ]
                    ),
                    updated_at=datetime.combine(anchor, time(11)),
                ),
            ]
        )
        db.session.commit()

    def test_analytics_report_tracks_core_metrics_and_risk_signals(self):
        anchor = date(2026, 7, 10)
        with self.app.app_context():
            self.seed_analytics(anchor)

            report = analytics_report("daily", anchor)

        metrics = report["metrics"]
        self.assertEqual(metrics["coding_hours"], 2.5)
        self.assertEqual(metrics["learning_hours"], 2.5)
        self.assertEqual(metrics["projects"], 2)
        self.assertEqual(metrics["hackathons"], 1)
        self.assertEqual(metrics["internships"], 1)
        self.assertEqual(metrics["emails"], 1)
        self.assertEqual(metrics["commits"], 1)
        self.assertEqual(metrics["tasks_completed"], 1)
        self.assertEqual(metrics["goals_completed"], 1)
        self.assertEqual(metrics["focus_time_hours"], 3.0)
        self.assertEqual(report["streaks"]["coding_days"], 3)
        self.assertEqual(report["burnout"]["level"], "low")
        self.assertFalse(report["inactivity"]["inactive"])
        self.assertTrue(report["workload_balance"])

    def test_analytics_generates_all_report_horizons_and_api_output(self):
        anchor = date(2026, 7, 10)
        with self.app.app_context():
            self.seed_analytics(anchor)
            overview = analytics_overview(anchor)

        self.assertEqual(set(overview["reports"].keys()), {"daily", "weekly", "monthly", "yearly"})
        self.assertEqual(overview["reports"]["weekly"]["start"], "2026-07-06")
        self.assertEqual(overview["reports"]["monthly"]["start"], "2026-07-01")
        self.assertEqual(overview["reports"]["yearly"]["start"], "2026-01-01")

        response = self.client.get(
            "/api/analytics?period=weekly&date=2026-07-10",
            headers={"X-AiOS-Token": "local-test-token"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["report"]["period"], "weekly")
        self.assertIn("burnout", payload["report"])

    def test_analytics_detects_inactivity(self):
        anchor = date(2026, 7, 10)
        with self.app.app_context():
            db.session.add(
                ActivityEvent(
                    source="collector",
                    app_name="VS Code",
                    category="coding",
                    duration_minutes=20,
                    created_at=datetime.combine(anchor - timedelta(days=5), time(10)),
                )
            )
            db.session.commit()

            report = analytics_report("daily", anchor)

        self.assertTrue(report["inactivity"]["inactive"])
        self.assertEqual(report["inactivity"]["days_since_activity"], 5)


if __name__ == "__main__":
    unittest.main()
