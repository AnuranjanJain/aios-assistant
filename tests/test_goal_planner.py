import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app


class GoalPlannerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "planner-test.db"

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            LOCAL_API_TOKEN = ""
            AI_PROVIDER = "rule_based"
            OLLAMA_URL = "http://127.0.0.1:9"
            OLLAMA_MODEL = "qwen2.5:3b"
            OLLAMA_EMBED_MODEL = "nomic-embed-text"
            MEMORY_VECTOR_BACKEND = "sqlite"
            MEMORY_VECTOR_PATH = str(Path(self.temp_dir.name) / "vectors")
            USER_DISPLAY_NAME = "Anuranjan"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.embedding_patch = patch("app.services.memory_engine.embed_text", return_value=[])
        self.embedding_patch.start()

    def tearDown(self):
        self.embedding_patch.stop()
        with self.app.app_context():
            from app.models import db

            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def test_operating_systems_roadmap_adapts_to_progress(self):
        response = self.client.post(
            "/api/planner",
            json={
                "goal": "I want to learn Operating Systems.",
                "cadence": "weekly",
                "duration_units": 3,
            },
        )
        self.assertEqual(response.status_code, 201)
        plan = response.get_json()
        self.assertEqual(plan["duration_units"], 3)
        self.assertEqual(plan["tasks"][0]["title"], "Processes")
        self.assertEqual(plan["tasks"][2]["title"], "CPU Scheduling")

        first_task = plan["tasks"][0]
        completed = self.client.post(
            f"/api/planner/tasks/{first_task['id']}/sessions",
            json={
                "duration_minutes": 324,
                "resources": ["OSTEP", "lecture notes"],
                "summary": "Learned process states and context switching.",
                "completed": True,
            },
        )
        self.assertEqual(completed.status_code, 201)
        task = completed.get_json()["task"]
        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["time_spent_minutes"], 324)
        self.assertEqual(task["suggested_next"], "Threads")

        overview = self.client.get("/api/planner").get_json()
        self.assertEqual(overview["counts"]["completed_tasks"], 1)
        self.assertEqual(overview["counts"]["minutes"], 324)


if __name__ == "__main__":
    unittest.main()
