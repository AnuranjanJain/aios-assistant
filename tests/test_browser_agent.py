import tempfile
import unittest
from pathlib import Path

from browser_agent import BrowserAgentEngine
from browser_agent.config import BrowserAgentConfig
from browser_agent.tools import BrowserResult


class FakeBrowser:
    def __init__(self):
        self.opened = ""
        self.closed = False

    def open(self, url):
        self.opened = url
        return BrowserResult(True, "Opened test jobs.", {"url": url})

    def extract_jobs(self, source="", **_arguments):
        return BrowserResult(
            True,
            "Extracted one job.",
            {
                "jobs": [
                    {
                        "source": source,
                        "source_url": "https://www.indeed.com/viewjob?jk=test",
                        "title": "Python Backend Intern",
                        "company": "Local AI Labs",
                        "description": "Python FastAPI SQL Docker internship",
                        "skills": ["python", "fastapi", "sql", "docker"],
                    }
                ]
            },
        )

    def extract_page(self, **_arguments):
        return BrowserResult(True, "Extracted page.", {"text": "Test"})

    def fill_form(self, **_arguments):
        return BrowserResult(True, "Prepared form.")

    def close(self):
        self.closed = True


class BrowserAgentTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        config = BrowserAgentConfig(
            data_dir=Path(self.temp_dir.name),
            allowed_domains=("indeed.com", "linkedin.com"),
        )
        self.backend = FakeBrowser()
        self.engine = BrowserAgentEngine(config, self.backend)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_job_research_scores_and_saves_opportunity(self):
        plan = self.engine.create_plan(
            "Find remote Python internships",
            {"source": "indeed", "query": "python internship"},
        )
        result = self.engine.execute_plan(
            plan["id"],
            profile={
                "skills": ["python", "fastapi", "sql"],
                "projects": ["docker", "python"],
                "resume_keywords": ["fastapi", "sql"],
            },
        )
        self.assertEqual(result["status"], "completed")
        jobs = self.engine.store.list_opportunities()
        self.assertEqual(len(jobs), 1)
        self.assertGreaterEqual(jobs[0]["match_score"], 70)
        self.assertTrue(self.backend.closed)

    def test_unknown_domain_is_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.create_plan(
                "Apply to this job",
                {"url": "https://untrusted.example/jobs/1"},
            )

    def test_apply_filters_is_a_search_not_a_submission(self):
        plan = self.engine.create_plan(
            "Apply filters on LinkedIn for remote Python internships",
            {"source": "linkedin", "query": "Python internship", "location": "Remote"},
        )
        self.assertEqual(plan["intent"], "job_search")
        self.assertEqual(plan["risk_level"], "low")
        self.assertNotIn("click_submit", [action["operation"] for action in plan["actions"]])

    def test_submission_stops_for_human_approval(self):
        plan = self.engine.create_plan(
            "Apply to this job",
            {
                "url": "https://www.linkedin.com/jobs/view/123",
                "fields": {"Name": "Anuranjan"},
            },
        )
        with self.assertRaises(PermissionError):
            self.engine.execute_plan(plan["id"])
        result = self.engine.execute_plan(plan["id"], plan["approval_token"])
        self.assertEqual(result["status"], "awaiting_approval")
        self.assertEqual(result["actions"][-1]["status"], "awaiting_approval")


if __name__ == "__main__":
    unittest.main()
