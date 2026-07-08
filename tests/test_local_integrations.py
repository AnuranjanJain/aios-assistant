import tempfile
import unittest
from pathlib import Path

from app import create_app


class LocalIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "integration-test.db"

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
            from app.models import db

            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def test_loopback_pairing_and_activity_ingest(self):
        pairing = self.client.get("/api/local/pairing")
        self.assertEqual(pairing.status_code, 200)
        self.assertEqual(pairing.get_json()["api_token"], "local-test-token")

        blocked = self.client.get(
            "/api/local/pairing",
            headers={"Origin": "https://example.com"},
        )
        self.assertEqual(blocked.status_code, 403)

        activity = self.client.post(
            "/api/wellbeing/activity",
            headers={"X-AiOS-Token": "local-test-token"},
            json={
                "source": "what-do-you-do-collector",
                "app_name": "Codex",
                "category": "deep_work",
                "duration_minutes": 12,
                "actual_task": "Building the local bridge",
            },
        )
        self.assertEqual(activity.status_code, 201)
        self.assertEqual(activity.get_json()["duration_minutes"], 12)


if __name__ == "__main__":
    unittest.main()
