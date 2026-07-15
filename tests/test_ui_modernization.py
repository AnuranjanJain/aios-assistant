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
        self.assertIn('aria-pressed="false">Overview</button>', html)

    def test_dashboard_detail_tabs_use_full_width_readable_layout(self):
        html = self.get_text("/?tab=opportunities")
        template = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
        self.assertIn('class="data-grid dashboard-detail-grid"', html)
        self.assertEqual(html.count("panel dashboard-detail-panel"), 3)
        self.assertEqual(html.count("list dashboard-detail-list"), 3)
        self.assertIn('class="list-meta"', template)

        css = Path("app/static/styles.css").read_text(encoding="utf-8")
        self.assertIn(".dashboard-detail-grid", css)
        self.assertIn("align-content: start", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", css)
        self.assertIn("repeat(auto-fit, minmax(min(100%, 360px), 1fr))", css)
        self.assertIn(".list-row .list-copy", css)
        self.assertIn(".list-meta > span + span::before", css)

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

        script = Path("app/static/app.js").read_text(encoding="utf-8")
        self.assertIn("setupInlineValidation", script)
        self.assertIn("field-error", script)
        self.assertIn("is-pending", script)

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
        self.assertIn("Connect Gmail to AiOS", html)
        self.assertIn("Sign in with Google", html)
        self.assertIn("Read-only Gmail access", html)
        self.assertNotIn("Google Desktop OAuth JSON", html)
        self.assertNotIn("Sync All Now", html)
        self.assertIn("GitHub token for private repo activity", html)
        self.assertIn("Email intelligence sync interval", html)
        self.assertIn("Test Ollama", html)
        self.assertIn('aria-label="Settings sections"', html)
        self.assertIn('href="#connected-accounts"', html)
        self.assertIn('aria-label="Checking desktop runtime"', html)
        self.assertNotIn("Checking desktop runtime...</p>", html)

    def test_desktop_show_route_reports_browser_mode(self):
        response = self.client.post("/api/desktop/show", json={"path": "/"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])

    def test_login_uses_accessible_shared_controls(self):
        html = self.get_text("/login")
        self.assertIn("<span>PIN</span>", html)
        self.assertIn("4 to 12 digits", html)
        self.assertIn("/static/design-system.css", html)
        self.assertIn("/static/app.js", html)

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

        design_css = Path("app/static/design-system.css").read_text(encoding="utf-8")
        self.assertIn("--ds-control: 44px", design_css)
        self.assertIn("--ds-radius-lg: 16px", design_css)
        self.assertIn("prefers-reduced-motion: reduce", design_css)
        self.assertIn("forced-colors: active", design_css)
        self.assertIn("[hidden]", design_css)
        self.assertIn(".planning-table th", design_css)
        self.assertIn("--ds-motion-expressive: 420ms", design_css)
        self.assertIn("@keyframes ds-reveal", design_css)
        self.assertIn("@media (hover: hover) and (pointer: fine)", design_css)
        self.assertIn(".oauth-wait-card", design_css)
        self.assertIn("@keyframes oauth-wait-progress", design_css)

        script = Path("app/static/app.js").read_text(encoding="utf-8")
        self.assertIn("setupRevealAnimations", script)
        self.assertIn("setupGoogleSignInWait", script)
        self.assertIn("data-oauth-cancel", script)
        self.assertIn("setupSidebarScrollPersistence", script)
        self.assertIn("aios.sidebar.scrollTop", script)
        self.assertIn('window.addEventListener("pagehide", savePosition)', script)
        self.assertIn("prefers-reduced-motion: reduce", script)
        self.assertIn("IntersectionObserver", script)

    def test_design_tokens_meet_text_contrast_targets(self):
        def luminance(hex_color):
            channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
            return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

        def contrast(first, second):
            bright, dark = sorted((luminance(first), luminance(second)), reverse=True)
            return (bright + 0.05) / (dark + 0.05)

        pairs = [
            ("#f4f7f2", "#121512"),
            ("#a7b0a4", "#121512"),
            ("#a7ff3c", "#121512"),
            ("#ff7b86", "#121512"),
            ("#10150c", "#a7ff3c"),
        ]
        for foreground, background in pairs:
            self.assertGreaterEqual(contrast(foreground, background), 4.5, (foreground, background))

    def test_shared_design_system_and_error_recovery_render(self):
        for path in ["/", "/planner", "/planning-events", "/settings", "/mobile"]:
            self.assertIn("/static/design-system.css", self.get_text(path), path)

        response = self.client.get("/page-that-does-not-exist")
        self.assertEqual(response.status_code, 404)
        html = response.get_data(as_text=True)
        for text in ["This page is not here", "Suggested fix", "Retry", "Go Back", "Copy Error", "Report Issue"]:
            self.assertIn(text, html)

        planner = self.get_text("/planning-events")
        self.assertIn('aria-label="Planning events table"', planner)
        self.assertIn('<caption class="sr-only">', planner)
        self.assertEqual(planner.count('scope="col"'), 10)

    def test_desktop_pages_share_one_base_layout(self):
        desktop_templates = [
            "automation.html",
            "browser_agent.html",
            "career.html",
            "connectors.html",
            "dashboard.html",
            "google_sign_in.html",
            "memory.html",
            "pipeline.html",
            "planner.html",
            "planning_events.html",
            "profile.html",
            "settings.html",
            "sources.html",
            "workers.html",
        ]
        for name in desktop_templates:
            source = Path("app/templates", name).read_text(encoding="utf-8")
            self.assertTrue(source.startswith('{% extends "base.html" %}'), name)
            self.assertNotIn("<!doctype html>", source, name)

        dashboard = self.get_text("/")
        self.assertIn('href="#main-content">Skip to content</a>', dashboard)
        self.assertIn('id="main-content"', dashboard)
        self.assertIn('class="page-loading-indicator"', dashboard)


if __name__ == "__main__":
    unittest.main()
