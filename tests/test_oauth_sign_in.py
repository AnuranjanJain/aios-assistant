import threading
import time
import unittest
from unittest import mock

from flask import Flask

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


if __name__ == "__main__":
    unittest.main()
