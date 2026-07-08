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
            "/gmail",
            "/hackathons",
            "/jobs",
            "/memory",
            "/planner",
            "/planning-events",
            "/profile",
            "/settings",
            "/sources",
            "/wellbeing",
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
        self.assertIn('href="/profile"', html)
        self.assertIn('href="/gmail"', html)
        self.assertIn('href="/hackathons"', html)
        self.assertIn('href="/jobs"', html)
        self.assertIn('href="/planning-events"', html)
        self.assertIn('href="/wellbeing"', html)
        self.assertIn('class="icon"', html)
        self.assertNotIn("nav-initial", html)
        self.assertNotIn(">Lock</button>", html)

    def test_forms_have_accessible_labels_and_loading_script(self):
        checks = {
            "/automation": ["Command", "Build Safe Preview"],
            "/browser-agent": ["Browser request", "Build Browser Plan"],
            "/career": ["Local path or GitHub URL", "Optimize Resume"],
            "/planner": ["Planning cadence", "Number of periods"],
            "/planning-events": ["Event title", "Work left", "Planned start"],
            "/sources": ["Choose export file", "Import Real Data"],
        }

        for path, expected_labels in checks.items():
            html = self.get_text(path)
            self.assertIn("/static/app.js", html, path)
            for label in expected_labels:
                self.assertIn(label, html, path)

    def test_settings_exposes_startup_services(self):
        html = self.get_text("/settings")
        self.assertIn("Launch AiOS with your desktop", html)
        self.assertIn("Start AiOS automatically", html)
        self.assertIn("Open in background tray mode", html)
        self.assertIn("Exit AiOS", html)
        self.assertIn("Real-life readiness", html)
        self.assertIn("Local-only privacy", html)
        self.assertIn("Gmail account", html)
        self.assertIn("Ollama loopback", html)
        self.assertIn("Planner rows", html)
        self.assertIn("Desktop services started by the app", html)
        self.assertIn("Desktop activity tracker", html)
        self.assertIn("Save Startup", html)
        self.assertIn("Connected Google accounts", html)
        self.assertIn("Connect Google Account", html)
        self.assertIn("Sync All Now", html)
        self.assertIn("GitHub token for private repo activity", html)
        self.assertIn("Email intelligence sync interval", html)
        self.assertIn("Test Ollama", html)

    def test_desktop_show_route_reports_browser_mode(self):
        response = self.client.post("/api/desktop/show", json={"path": "/"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_stylesheet_contains_responsive_sidebar_and_accessibility_guards(self):
        css = Path("app/static/styles.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: 248px minmax(0, 1fr)", css)
        self.assertIn(".nav-label", css)
        self.assertIn("text-overflow: ellipsis", css)
        self.assertIn("overflow-y: auto", css)
        self.assertIn("@media (max-width: 1100px)", css)
        self.assertIn("flex: 0 0 auto", css)
        self.assertIn(":focus-visible", css)
        self.assertIn(".empty::before", css)
        self.assertIn(".desktop-toast", css)
        self.assertIn(".confidence-stat", css)
        self.assertIn("pageOut", css)


if __name__ == "__main__":
    unittest.main()
