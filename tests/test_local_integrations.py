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

        desktop_origin = self.client.get(
            "/settings",
            base_url="http://127.0.0.1:5050",
            headers={"Origin": "http://127.0.0.1:5050"},
        )
        self.assertEqual(desktop_origin.status_code, 200)

        desktop_post = self.client.post(
            "/settings",
            base_url="http://127.0.0.1:5050",
            headers={"Origin": "http://localhost:5050"},
            data={},
        )
        self.assertEqual(desktop_post.status_code, 200)

        webview_post = self.client.post(
            "/settings",
            base_url="http://127.0.0.1:5050",
            headers={
                "Origin": "null",
                "Referer": "http://127.0.0.1:5050/settings",
                "Sec-Fetch-Site": "same-origin",
            },
            data={},
        )
        self.assertEqual(webview_post.status_code, 200)

        token_page = self.client.get("/settings", base_url="http://127.0.0.1:5050")
        self.assertEqual(token_page.status_code, 200)
        form_token = self.client.get_cookie("aios_form_token", domain="127.0.0.1").value
        opaque_webview_post = self.client.post(
            "/settings",
            base_url="http://127.0.0.1:5050",
            headers={"Origin": "null", "Sec-Fetch-Site": "none"},
            data={"_local_form_token": form_token},
        )
        self.assertEqual(opaque_webview_post.status_code, 200)

        missing_webview_proof = self.client.post(
            "/settings",
            base_url="http://127.0.0.1:5050",
            headers={"Origin": "null"},
            data={},
        )
        self.assertEqual(missing_webview_proof.status_code, 403)
        self.assertIn("AiOS blocked an unsafe request", missing_webview_proof.get_data(as_text=True))
        self.assertIn("Go Back", missing_webview_proof.get_data(as_text=True))

        cross_site_webview_post = self.client.post(
            "/settings",
            base_url="http://127.0.0.1:5050",
            headers={
                "Origin": "null",
                "Referer": "https://example.com/settings",
                "Sec-Fetch-Site": "same-origin",
            },
            data={},
        )
        self.assertEqual(cross_site_webview_post.status_code, 403)

        blocked_api_payload = blocked.get_json()
        self.assertEqual(blocked_api_payload["error"], "origin_not_allowed")
        self.assertIn("suggested_fix", blocked_api_payload)

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
