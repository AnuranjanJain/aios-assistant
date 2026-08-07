import threading
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from flask import Flask

from app import create_app
from app.models import db
import app.services.oauth_sign_in as oauth_sign_in
from app.services.oauth_sign_in import (
    cancel_google_sign_in,
    consume_google_sign_in_result,
    continue_google_sign_in,
    get_google_sign_in,
    start_google_sign_in,
)


class GoogleSignInJobTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def wait_for(self, job_id, expected, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = get_google_sign_in(job_id)
            if job and job["status"] == expected:
                return job
            time.sleep(0.01)
        self.fail(f"Google sign-in job did not reach {expected}")

    def test_waiting_job_can_reopen_browser_and_cancel_without_storing_access(self):
        ready = threading.Event()

        def connector(_config, label, on_authorization, should_cancel):
            self.assertEqual(label, "Personal")
            on_authorization("https://accounts.google.com/o/oauth2/v2/auth?state=local-test")
            ready.set()
            while not should_cancel():
                time.sleep(0.01)
            return {"ok": False, "status": "cancelled", "message": "Google sign-in was cancelled."}

        job = start_google_sign_in(self.app, {}, label="Personal", connector=connector)
        self.assertTrue(ready.wait(1))
        waiting = self.wait_for(job["id"], "waiting")
        self.assertTrue(waiting["can_continue"])

        with mock.patch("app.services.oauth_sign_in.webbrowser.open", return_value=True) as open_browser:
            reopened = continue_google_sign_in(job["id"])
        self.assertTrue(reopened["ok"])
        open_browser.assert_called_once()

        cancelled = cancel_google_sign_in(job["id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertTrue(cancelled["terminal"])
        self.assertFalse(cancelled["can_continue"])
        self.assertFalse(consume_google_sign_in_result(job["id"])["ok"])

    def test_successful_job_preserves_result_until_settings_consumes_it(self):
        def connector(_config, label, on_authorization, should_cancel):
            on_authorization("https://accounts.google.com/o/oauth2/v2/auth?state=success-test")
            self.assertFalse(should_cancel())
            return {"ok": True, "message": f"Connected {label}"}

        job = start_google_sign_in(self.app, {}, label="me@example.com", connector=connector)
        completed = self.wait_for(job["id"], "succeeded")
        self.assertTrue(completed["terminal"])
        result = consume_google_sign_in_result(job["id"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "Connected me@example.com")
        self.assertIsNone(get_google_sign_in(job["id"]))

    def test_job_survives_process_registry_loss_when_database_is_available(self):
        with tempfile.TemporaryDirectory(prefix="aios-oauth-job-") as directory:
            database_path = Path(directory) / "aios.db"

            class TestConfig:
                TESTING = True
                SECRET_KEY = "oauth-job-test"
                SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
                SQLALCHEMY_TRACK_MODIFICATIONS = False
                AIOS_DATA_DIR = directory
                MEMORY_VECTOR_BACKEND = "sqlite"
                MEMORY_VECTOR_PATH = str(Path(directory) / "vectors")
                USER_DISPLAY_NAME = "Test User"

            app = create_app(TestConfig)

            def connector(_config, label, on_authorization, should_cancel):
                on_authorization("https://accounts.google.com/o/oauth2/v2/auth?state=persisted")
                self.assertEqual(label, "Persisted")
                self.assertFalse(should_cancel())
                return {"ok": True, "message": "Connected Persisted"}

            job = start_google_sign_in(app, {}, label="Persisted", connector=connector)
            completed = self.wait_for(job["id"], "succeeded")
            self.assertTrue(completed["terminal"])

            with oauth_sign_in._LOCK:
                oauth_sign_in._JOBS.clear()

            restored = get_google_sign_in(job["id"], app=app)
            self.assertEqual(restored["status"], "succeeded")
            self.assertTrue(consume_google_sign_in_result(job["id"], app=app)["ok"])

            with app.app_context():
                self.assertIsNone(db.session.get(oauth_sign_in.OAuthSignInJob, job["id"]))
                interrupted = oauth_sign_in.OAuthSignInJob(
                    id="restarted-job",
                    status="waiting",
                    message="Finish choosing your Google account in the browser.",
                    authorization_url="https://accounts.google.com/recover",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.session.add(interrupted)
                db.session.commit()
                db.session.remove()
                db.engine.dispose()

            with oauth_sign_in._LOCK:
                oauth_sign_in._JOBS.clear()
            recovered = get_google_sign_in("restarted-job", app=app)
            self.assertEqual(recovered["status"], "failed")
            self.assertFalse(recovered["can_continue"])
            self.assertIn("restarted", recovered["message"])
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
