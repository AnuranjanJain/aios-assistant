import tempfile
import unittest
import json
from unittest import mock
from pathlib import Path
from datetime import date, datetime, time, timedelta

from app import create_app
from app.models import ConnectedAccount, EmailMessage, EmailTask, Opportunity, PlanningEvent, db
from app.services.email_intelligence import (
    analyze_pending_emails,
    decrypt_token_json,
    encrypt_token_json,
    generate_daily_plan,
    intelligence_summary,
    run_email_intelligence_cycle,
)
from app.services.planning_events import create_manual_event, planning_board, update_event_progress
from app.services.readiness import readiness_summary
from app.services.settings import set_setting
from email_intelligence_worker import sync_interval_seconds


class EmailIntelligenceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "email-intelligence.db"

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            LOCAL_API_TOKEN = "local-test-token"
            AI_PROVIDER = "rule_based"
            OLLAMA_URL = "http://127.0.0.1:9"
            OLLAMA_MODEL = "qwen2.5:3b"
            OLLAMA_EMBED_MODEL = "nomic-embed-text"
            MEMORY_VECTOR_BACKEND = "sqlite"
            MEMORY_VECTOR_PATH = str(Path(self.temp_dir.name) / "vectors")
            USER_DISPLAY_NAME = "Anuranjan"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_oauth_token_encryption_round_trips(self):
        token = '{"refresh_token":"secret-refresh-token"}'
        encrypted = encrypt_token_json(token)

        self.assertNotIn("secret-refresh-token", encrypted)
        self.assertEqual(decrypt_token_json(encrypted), token)

    def test_email_analysis_generates_local_plan_summary(self):
        account = ConnectedAccount(provider="google", email="me@example.com", label="Main")
        db.session.add(account)
        db.session.flush()
        db.session.add(
            EmailMessage(
                account=account,
                provider_message_id="gmail-1",
                sender="client@example.com",
                subject="Can you finish this by Friday?",
                snippet="Please finish the dashboard by Friday.",
                body_text="Can you finish this by Friday? We need it for review.",
                is_unread=True,
            )
        )
        db.session.commit()

        result = analyze_pending_emails(app_config={"AI_PROVIDER": "rule_based"})
        plan = generate_daily_plan()
        summary = intelligence_summary()
        task = EmailTask.query.first()

        self.assertEqual(result["analyzed"], 1)
        self.assertGreaterEqual(summary["urgent_emails"], 1)
        self.assertIn("urgent email", plan["summary"])
        self.assertEqual(summary["accounts"], 1)
        self.assertIsNotNone(task.due_at)
        self.assertEqual(task.due_at.hour, 17)
        email_events = summary["planning_events"]["events"]
        self.assertEqual(email_events[0]["event_type"], "email")
        self.assertIsNotNone(email_events[0]["deadline"])
        self.assertEqual(
            datetime.fromisoformat(email_events[0]["planned_start"]),
            datetime.fromisoformat(email_events[0]["deadline"]) - timedelta(hours=2),
        )
        self.assertGreaterEqual(len(summary["planning_events"]["plan_blocks"]["week"]), 1)

    def test_intelligence_today_api_is_loopback_client_ready(self):
        response = self.client.get("/api/intelligence/today", headers={"X-AiOS-Token": "local-test-token"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertIn("planning_events", response.get_json())

    def test_live_api_exposes_real_life_readiness(self):
        response = self.client.get("/api/live")
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("readiness", payload)
        self.assertEqual(payload["readiness"]["total"], 7)
        self.assertIn("items", payload["readiness"])

    def test_settings_page_manages_connected_email_accounts(self):
        account = ConnectedAccount(provider="google", email="me@example.com", label="Main Gmail")
        db.session.add(account)
        db.session.commit()

        html = self.client.get("/settings").get_data(as_text=True)
        self.assertIn("Connect Google Account", html)
        self.assertIn("Sync All Now", html)
        self.assertIn("Main Gmail", html)
        self.assertIn("Pause", html)

        rename = self.client.post(
            "/settings",
            data={
                "settings_action": "rename_email_account",
                "account_id": str(account.id),
                "label": "College Gmail",
            },
        )
        self.assertEqual(rename.status_code, 200)
        self.assertEqual(db.session.get(ConnectedAccount, account.id).label, "College Gmail")

        pause = self.client.post(
            "/settings",
            data={"settings_action": "pause_email_account", "account_id": str(account.id)},
        )
        self.assertEqual(pause.status_code, 200)
        self.assertFalse(db.session.get(ConnectedAccount, account.id).sync_enabled)

        resume = self.client.post(
            "/settings",
            data={"settings_action": "resume_email_account", "account_id": str(account.id)},
        )
        self.assertEqual(resume.status_code, 200)
        self.assertTrue(db.session.get(ConnectedAccount, account.id).sync_enabled)

        remove = self.client.post(
            "/settings",
            data={"settings_action": "remove_email_account", "account_id": str(account.id)},
        )
        self.assertEqual(remove.status_code, 200)
        self.assertIsNone(db.session.get(ConnectedAccount, account.id))

    def test_readiness_summary_tracks_real_life_setup_state(self):
        values = {
            "OLLAMA_URL": "http://127.0.0.1:11434",
            "OLLAMA_MODEL": "qwen2.5:3b",
            "EMAIL_SYNC_INTERVAL_MINUTES": "7",
            "GITHUB_TOKEN": "ghp_test",
        }
        db.session.add(ConnectedAccount(provider="google", email="me@example.com", label="Main Gmail"))
        create_manual_event(
            {
                "event_type": "goal",
                "title": "Ship WDYD planner",
                "project": "WDYD",
                "work_left": "Wire the readiness panel",
            }
        )
        db.session.commit()

        summary = readiness_summary(values)
        items = {item["id"]: item for item in summary["items"]}

        self.assertTrue(items["privacy"]["ok"])
        self.assertTrue(items["gmail_account"]["ok"])
        self.assertTrue(items["gmail_sync"]["ok"])
        self.assertTrue(items["ollama"]["ok"])
        self.assertTrue(items["github"]["ok"])
        self.assertTrue(items["planner"]["ok"])
        self.assertIn("1 real-life rows", items["planner"]["detail"])
        self.assertIn("Answer waiting questions", items["planner"]["action"])
        self.assertIn("ollama pull qwen2.5:3b", items["ollama"]["action"])
        self.assertEqual(summary["total"], 7)

    def test_settings_ollama_check_rejects_non_loopback_url(self):
        response = self.client.post(
            "/settings",
            data={
                "settings_action": "test_ollama",
                "OLLAMA_URL": "https://example.com",
                "OLLAMA_MODEL": "qwen2.5:3b",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Ollama URL must stay on loopback", html)

    def test_hackathon_source_generates_command_planner_row(self):
        db.session.add(
            Opportunity(
                kind="hackathon",
                title="FlightIQ Challenge",
                organization="Build Club",
                status="Tracked",
                source="https://example.com/challenge",
                deadline=datetime.utcnow() + timedelta(days=5),
                notes="Repo: https://example.com/anura/flightiq. Build demo, submit video, and polish README.",
            )
        )
        db.session.commit()

        board = planning_board()

        self.assertEqual(board["counts"]["hackathons"], 1)
        self.assertEqual(board["counts"]["week"], 1)
        self.assertEqual(board["counts"]["month"], 1)
        self.assertEqual(len(board["agenda"]["week"]), 1)
        self.assertEqual(len(board["agenda"]["month"]), 1)
        self.assertEqual(len(board["plan_blocks"]["week"]), 1)
        self.assertIn("Build demo", board["plan_blocks"]["week"][0]["next_action"])
        self.assertEqual(board["briefing"]["week_count"], 1)
        self.assertIn("FlightIQ Challenge", board["briefing"]["focus"])
        self.assertEqual(len(board["question_queue"]), 1)
        self.assertIn("FlightIQ Challenge", board["question_queue"][0]["question"])
        event = board["events"][0]
        self.assertEqual(event["event_type"], "hackathon")
        self.assertEqual(event["title"], "FlightIQ Challenge")
        self.assertIn("submit video", event["work_left"])
        self.assertIn("FlightIQ Challenge", event["next_question"])
        planned_start = datetime.fromisoformat(event["planned_start"])
        deadline = datetime.fromisoformat(event["deadline"])
        self.assertLess(planned_start, deadline)
        self.assertEqual(planned_start.date(), (deadline - timedelta(days=2)).date())
        self.assertIn(planned_start.hour, {9, 11, 14, 16, 19})

        update_event_progress(
            event["id"],
            {
                "status": "in_progress",
                "planned_start": "2026-06-20T14:30",
                "planned_minutes": 120,
                "work_done": "Built landing page and pushed initial repo.",
                "work_left": "Add demo video and final README.",
                "progress_note": "Today I finished the pitch copy.",
            },
        )
        refreshed = planning_board()["events"][0]
        self.assertEqual(refreshed["status"], "in_progress")
        self.assertEqual(refreshed["planned_start"], "2026-06-20T14:30:00")
        self.assertEqual(refreshed["planned_minutes"], 120)
        self.assertIn("Built landing page", refreshed["work_done"])
        self.assertEqual(refreshed["last_progress_note"], "Today I finished the pitch copy.")
        self.assertEqual(refreshed["metadata"]["progress_log"][0]["note"], "Today I finished the pitch copy.")
        queue = planning_board()["question_queue"][0]
        self.assertEqual(queue["last_progress_note"], "Today I finished the pitch copy.")

    def test_manual_learning_video_event_can_be_updated(self):
        result = create_manual_event(
            {
                "event_type": "learning_video",
                "title": "Finish Qwen local LLM tutorial",
                "project": "WDYD AI planning",
                "planned_minutes": 50,
                "work_left": "Watch part two and save notes.",
            }
        )

        self.assertTrue(result["ok"])
        event_id = result["event"]["id"]
        update = update_event_progress(
            event_id,
            {
                "status": "in_progress",
                "work_done": "Completed intro and wrote setup notes.",
                "work_left": "Try embeddings locally.",
                "progress_note": "Video one is done; notes saved in my GenAI notebook.",
            },
        )

        self.assertTrue(update["ok"])
        self.assertEqual(update["event"]["status"], "in_progress")
        self.assertIn("Completed intro", update["event"]["work_done"])
        self.assertIn("Which video did you complete", update["event"]["next_question"])

        saved = db.session.get(PlanningEvent, event_id)
        self.assertEqual(saved.event_type, "learning_video")
        self.assertIn("progress_log", update["event"]["metadata"])

    def test_planning_event_api_creates_real_life_row_from_wdyd(self):
        response = self.client.post(
            "/api/planning-events",
            headers={"X-AiOS-Token": "local-test-token"},
            json={
                "event_type": "learning_video",
                "title": "Finish GenAI attention video",
                "project": "GenAI",
                "idea": "Understand attention before building the demo.",
                "deadline": "2026-07-12T18:00:00",
                "planned_start": "2026-07-10T09:00:00",
                "planned_minutes": 60,
                "work_done": "Watched embeddings chapter.",
                "work_left": "Finish attention video and save notes.",
                "repo_url": "https://github.com/anura/genai-notes",
            },
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["event"]["event_type"], "learning_video")
        self.assertEqual(payload["event"]["project"], "GenAI")
        self.assertEqual(payload["event"]["planned_minutes"], 60)
        self.assertIn("attention", payload["event"]["idea"])
        self.assertIn("Which video did you complete", payload["event"]["next_question"])

        board = self.client.get(
            "/api/planning-events",
            headers={"X-AiOS-Token": "local-test-token"},
        ).get_json()
        self.assertEqual(board["counts"]["total"], 1)
        self.assertEqual(board["events"][0]["title"], "Finish GenAI attention video")
        self.assertEqual(board["plan_blocks"]["month"][0]["duration_minutes"], 60)

    def test_email_sync_cycle_reports_planner_follow_up_counts(self):
        create_manual_event(
            {
                "event_type": "learning_video",
                "title": "Finish GenAI attention video",
                "project": "GenAI",
                "deadline": "2026-07-12T18:00:00",
                "planned_start": "2026-07-10T09:00:00",
                "planned_minutes": 60,
                "work_left": "Finish attention video and save notes.",
            }
        )

        result = run_email_intelligence_cycle({"AI_PROVIDER": "rule_based"})

        self.assertEqual(result["planning"]["rows"], 1)
        self.assertEqual(result["planning"]["month"], 1)
        self.assertEqual(result["planning"]["questions"], 1)
        self.assertIn("analysis", result)

    def test_planning_engine_creates_required_horizons_without_overbooking(self):
        today = date.today()
        rows = [
            PlanningEvent(
                source_key="manual:today-deep-work",
                event_type="repo",
                source="manual",
                title="Today repo sprint",
                priority="high",
                deadline=datetime.combine(today, time(17)),
                planned_minutes=60,
                metadata_json=json.dumps(
                    {
                        "energy_level": "high",
                        "difficulty": "hard",
                        "calendar_events": [
                            {
                                "start": datetime.combine(today, time(9)).isoformat(),
                                "end": datetime.combine(today, time(10)).isoformat(),
                            }
                        ],
                    }
                ),
            ),
            PlanningEvent(
                source_key="manual:today-second-block",
                event_type="goal",
                source="manual",
                title="Today learning block",
                priority="normal",
                deadline=datetime.combine(today, time(18)),
                planned_minutes=60,
            ),
            PlanningEvent(
                source_key="manual:tomorrow-block",
                event_type="email",
                source="manual",
                title="Tomorrow follow-up",
                priority="normal",
                deadline=datetime.combine(today + timedelta(days=1), time(17)),
                planned_start=datetime.combine(today + timedelta(days=1), time(11)),
                planned_minutes=45,
            ),
            PlanningEvent(
                source_key="manual:next-week-block",
                event_type="hackathon",
                source="manual",
                title="Next week hackathon work",
                priority="high",
                deadline=datetime.combine(today + timedelta(days=9), time(17)),
                planned_start=datetime.combine(today + timedelta(days=8), time(14)),
                planned_minutes=90,
            ),
            PlanningEvent(
                source_key="manual:month-block",
                event_type="learning_video",
                source="manual",
                title="Monthly GenAI lesson",
                priority="low",
                deadline=datetime.combine(today + timedelta(days=20), time(17)),
                planned_start=datetime.combine(today + timedelta(days=20), time(19)),
                planned_minutes=50,
            ),
        ]
        db.session.add_all(rows)
        db.session.commit()

        blocks = planning_board()["plan_blocks"]

        self.assertGreaterEqual(len(blocks["today"]), 2)
        self.assertGreaterEqual(len(blocks["tomorrow"]), 1)
        self.assertGreaterEqual(len(blocks["week"]), 3)
        self.assertGreaterEqual(len(blocks["next_week"]), 1)
        self.assertGreaterEqual(len(blocks["month"]), 5)
        today_blocks = sorted(blocks["today"], key=lambda item: item["start"])
        first_start = datetime.fromisoformat(today_blocks[0]["start"])
        second_start = datetime.fromisoformat(today_blocks[1]["start"])
        first_end = first_start + timedelta(minutes=today_blocks[0]["duration_minutes"])
        self.assertGreaterEqual(first_start.time(), time(10))
        self.assertGreaterEqual(second_start, first_end)

    def test_planning_engine_respects_dependencies_progress_and_recalculates(self):
        today = date.today()
        dependency = PlanningEvent(
            source_key="manual:dependency",
            event_type="goal",
            source="manual",
            title="Finish prerequisite",
            status="planned",
            planned_minutes=30,
        )
        dependent = PlanningEvent(
            source_key="manual:dependent",
            event_type="goal",
            source="manual",
            title="Dependent project work",
            deadline=datetime.combine(today + timedelta(days=3), time(17)),
            planned_minutes=120,
            metadata_json=json.dumps({"dependencies": ["manual:dependency"], "progress": 0.5}),
        )
        db.session.add_all([dependency, dependent])
        db.session.commit()

        board = planning_board()
        scheduled_titles = {item["title"] for item in board["plan_blocks"]["week"]}
        self.assertNotIn("Dependent project work", scheduled_titles)

        dependency.status = "done"
        db.session.commit()
        board = planning_board()
        dependent_block = next(item for item in board["plan_blocks"]["week"] if item["title"] == "Dependent project work")
        self.assertEqual(dependent_block["duration_minutes"], 60)

        dependent.deadline = datetime.combine(today + timedelta(days=10), time(17))
        db.session.commit()
        board = planning_board()
        next_week_titles = {item["title"] for item in board["plan_blocks"]["next_week"]}
        self.assertIn("Dependent project work", next_week_titles)

    def test_planning_engine_respects_meetings_preferred_hours_and_sleep(self):
        today = date.today()
        meeting = PlanningEvent(
            source_key="calendar:team-sync",
            event_type="meeting",
            source="calendar",
            title="Team sync",
            planned_start=datetime.combine(today, time(13)),
            planned_minutes=60,
            status="planned",
        )
        task = PlanningEvent(
            source_key="manual:preferred-after-meeting",
            event_type="repo",
            source="manual",
            title="Repo review after meeting",
            priority="high",
            deadline=datetime.combine(today, time(17)),
            planned_minutes=45,
            metadata_json=json.dumps(
                {
                    "preferred_working_hours": [{"start": "13:00", "end": "15:00"}],
                    "energy_level": "low",
                    "sleep_schedule": {"start": "23:00", "end": "07:00"},
                }
            ),
        )
        sleeping_task = PlanningEvent(
            source_key="manual:sleep-blocked",
            event_type="goal",
            source="manual",
            title="Too late deep work",
            priority="normal",
            deadline=datetime.combine(today, time(23)),
            planned_minutes=90,
            metadata_json=json.dumps(
                {
                    "preferred_working_hours": [{"start": "21:30", "end": "23:30"}],
                    "sleep_schedule": {"start": "22:00", "end": "07:00"},
                }
            ),
        )
        db.session.add_all([meeting, task, sleeping_task])
        db.session.commit()

        today_blocks = planning_board()["plan_blocks"]["today"]
        review = next(item for item in today_blocks if item["title"] == "Repo review after meeting")
        review_start = datetime.fromisoformat(review["start"])
        self.assertGreaterEqual(review_start.time(), time(14))
        self.assertNotIn("Too late deep work", {item["title"] for item in today_blocks})

    def test_github_token_is_used_for_repo_activity_refresh(self):
        set_setting("GITHUB_TOKEN", "ghp_local_test")
        event = PlanningEvent(
            source_key="manual:private-repo-test",
            event_type="repo",
            source="manual",
            title="Private repo polish",
            repo_url="https://github.com/example/private-repo",
        )
        db.session.add(event)
        db.session.commit()

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                if "commits" in self.url:
                    return (
                        b'[{"commit":{"message":"ship private planner","committer":{"date":"2026-06-20T10:00:00Z"}}},'
                        b'{"commit":{"message":"add repo notes","committer":{"date":"2026-06-19T10:00:00Z"}}}]'
                    )
                if "type:issue" in self.url:
                    return b'{"total_count":2,"items":[]}'
                return b'{"total_count":1,"items":[]}'

        captured = {}

        def fake_urlopen(request, timeout):
            captured.setdefault("authorization", []).append(request.headers.get("Authorization"))
            captured.setdefault("urls", []).append(request.full_url)
            captured["timeout"] = timeout
            FakeResponse.url = request.full_url
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            from app.services.planning_events import refresh_repo_activity

            refresh_repo_activity(event)

        self.assertEqual(captured["authorization"], ["Bearer ghp_local_test"] * 3)
        self.assertEqual(captured["timeout"], 2.5)
        self.assertEqual(len(captured["urls"]), 3)
        self.assertIn("ship private planner", event.repo_latest_activity)
        self.assertIn("add repo notes", event.repo_latest_activity)
        self.assertIn("2 issues, 1 PRs", event.repo_latest_activity)

    def test_email_sync_interval_is_configurable_with_safe_floor(self):
        set_setting("EMAIL_SYNC_INTERVAL_MINUTES", "1")
        db.session.commit()
        self.assertEqual(sync_interval_seconds(self.app), 120)

        set_setting("EMAIL_SYNC_INTERVAL_MINUTES", "7")
        db.session.commit()
        self.assertEqual(sync_interval_seconds(self.app), 420)


if __name__ == "__main__":
    unittest.main()
