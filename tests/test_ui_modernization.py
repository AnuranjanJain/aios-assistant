import tempfile
import unittest
from pathlib import Path

from app import create_app


class UiModernizationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "ui-modernization.db"

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            LOCAL_API_TOKEN = "local-test-token"
            OLLAMA_URL = "http://127.0.0.1:9"
            OLLAMA_MODEL = "qwen2.5:7b"
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

    def get_text(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.get_data(as_text=True)

    def test_core_desktop_routes_render_without_glyph_artifacts(self):
        bad_characters = [chr(0x00C2), chr(0x00E2), chr(0xFFFD)]
        paths = [
            "/",
            "/automation",
            "/browser-agent",
            "/career",
            "/connectors",
            "/memory",
            "/planner",
            "/settings",
            "/sources",
            "/workers",
        ]

        for path in paths:
            html = self.get_text(path)
            for bad_character in bad_characters:
                self.assertNotIn(bad_character, html, path)

    def test_dashboard_sidebar_keeps_real_labels_and_lock_copy(self):
        html = self.get_text("/")
        self.assertIn("Anuranjan", html)
        self.assertIn("Lock workspace", html)
        self.assertIn('class="nav-label">Overview</span>', html)
        self.assertIn('class="nav-label">Browser Agent</span>', html)
        self.assertIn('class="nav-label">Career Copilot</span>', html)
        self.assertNotIn(">Lock</button>", html)

    def test_forms_have_accessible_labels_and_loading_script(self):
        checks = {
            "/automation": ["Command", "Build Safe Preview"],
            "/browser-agent": ["Browser request", "Build Browser Plan"],
            "/career": ["Local path or GitHub URL", "Optimize Resume"],
            "/planner": ["Planning cadence", "Number of periods"],
            "/sources": ["Choose export file", "Import Real Data"],
        }

        for path, expected_labels in checks.items():
            html = self.get_text(path)
            self.assertIn("/static/app.js", html, path)
            for label in expected_labels:
                self.assertIn(label, html, path)

    def test_stylesheet_contains_responsive_sidebar_and_accessibility_guards(self):
        css = Path("app/static/styles.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: 248px minmax(0, 1fr)", css)
        self.assertIn(".nav-label", css)
        self.assertIn("text-overflow: ellipsis", css)
        self.assertIn("@media (max-width: 1100px)", css)
        self.assertIn("flex: 0 0 auto", css)
        self.assertIn(":focus-visible", css)
        self.assertIn(".empty::before", css)
        self.assertIn(".desktop-toast", css)


if __name__ == "__main__":
    unittest.main()
