import tempfile
import unittest
import json
import sqlite3
from unittest import mock
from pathlib import Path
from datetime import date, datetime, time, timedelta

from app import create_app
from app.models import (
    ConnectedAccount,
    DailyAssistantEntry,
    EmailAttachment,
    EmailInsight,
    EmailMessage,
    EmailTask,
    GitHubDailySummary,
    GitHubRepository,
    EmailThread,
    LearningItem,
    LifeItem,
    LifeItemRelation,
    MemoryEntity,
    MemoryFact,
    Opportunity,
    PlanTask,
    GoalPlan,
    PlanningEvent,
    WorkCheckpoint,
    db,
)
from app.services.email_intelligence import (
    _gmail_message_ids,
    analyze_pending_emails,
    decrypt_token_json,
    encrypt_token_json,
    generate_daily_plan,
    intelligence_summary,
    run_email_intelligence_cycle,
    upsert_gmail_message,
)
from app.services.github_intelligence import update_all_repositories, update_repository
from app.services.learning_intelligence import evening_questions, learning_summary, record_learning_progress, upsert_learning_item
from app.services.daily_assistant import generate_morning_briefing, evening_checkin_prompt, submit_evening_checkin
from app.services.knowledge_graph import build_knowledge_graph, query_knowledge_graph
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

    def test_gmail_upsert_preserves_thread_labels_and_attachment_metadata(self):
        account = ConnectedAccount(provider="google", email="me@example.com", label="Main")
        db.session.add(account)
        db.session.flush()

        imported = upsert_gmail_message(
            account,
            {
                "id": "gmail-sync-1",
                "threadId": "thread-1",
                "historyId": "110",
                "labelIds": ["INBOX", "IMPORTANT", "STARRED", "UNREAD"],
                "snippet": "Please review the attached brief.",
                "internalDate": "1783766400000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "recruiter@amazon.com"},
                        {"name": "To", "value": "me@example.com"},
                        {"name": "Subject", "value": "Internship brief and resume request"},
                    ],
                    "parts": [
                        {
                            "mimeType": "text/plain",
                            "body": {"data": "UGxlYXNlIHNlbmQgeW91ciByZXN1bWUgYnkgRnJpZGF5Lg=="},
                        },
                        {
                            "filename": "brief.pdf",
                            "mimeType": "application/pdf",
                            "body": {"attachmentId": "att-1", "size": 12345},
                        },
                    ],
                },
            },
        )
        db.session.commit()

        message = EmailMessage.query.filter_by(provider_message_id="gmail-sync-1").first()
        thread = EmailThread.query.filter_by(provider_thread_id="thread-1").first()
        attachment = EmailAttachment.query.filter_by(email_id=message.id).first()

        self.assertTrue(imported)
        self.assertEqual(account.sync_cursor, "110")
        self.assertEqual(message.thread_id, thread.id)
        self.assertTrue(message.is_unread)
        self.assertIn("IMPORTANT", json.loads(message.labels_json))
        self.assertIn("STARRED", json.loads(thread.labels_json))
        self.assertIn("resume by Friday", message.body_text)
        self.assertEqual(attachment.filename, "brief.pdf")
        self.assertEqual(attachment.provider_attachment_id, "att-1")
        self.assertEqual(attachment.size_bytes, 12345)

    def test_incremental_history_sync_collects_message_ids_and_updates_cursor(self):
        class FakeExecute:
            def __init__(self, payload):
                self.payload = payload

            def execute(self):
                return self.payload

        class FakeHistory:
            def list(self, **_kwargs):
                return FakeExecute(
                    {
                        "historyId": "220",
                        "history": [
                            {"messagesAdded": [{"message": {"id": "m-1"}}]},
                            {"labelsAdded": [{"message": {"id": "m-2"}}, {"message": {"id": "m-1"}}]},
                        ],
                    }
                )

        class FakeUsers:
            def history(self):
                return FakeHistory()

        class FakeService:
            def users(self):
                return FakeUsers()

        account = ConnectedAccount(provider="google", email="me@example.com", label="Main", sync_cursor="100")
        ids = _gmail_message_ids(FakeService(), account, limit=10)

        self.assertEqual(ids, ["m-1", "m-2"])
        self.assertEqual(account.sync_cursor, "220")

    def test_internship_email_extracts_fields_and_creates_related_life_item(self):
        account = ConnectedAccount(provider="google", email="me@example.com", label="Main")
        existing = LifeItem(
            source_key="manual:flightiq",
            title="FlightIQ dashboard",
            description="Hackathon repository and internship portfolio project for Amazon.",
            category="hackathon",
            priority="high",
            repository="https://github.com/anura/flightiq",
            tags_json=json.dumps(["FlightIQ", "Amazon"]),
        )
        db.session.add_all([account, existing])
        db.session.flush()
        db.session.add(
            EmailMessage(
                account=account,
                provider_message_id="gmail-internship-1",
                provider_thread_id="thread-internship",
                sender='"Riya Sharma" <recruiter@amazon.com>',
                subject="Amazon internship documents for FlightIQ by Friday",
                snippet="Please send your resume, transcript, and GitHub repository before the interview.",
                body_text=(
                    "Hi, for the Amazon internship interview please send your resume, transcript, "
                    "and project repository https://github.com/anura/flightiq by Friday. "
                    "We will schedule a Zoom interview call after that."
                ),
                labels_json=json.dumps(["INBOX", "IMPORTANT"]),
                is_unread=True,
                sent_at=datetime(2026, 7, 6, 9, 0),
            )
        )
        db.session.commit()

        result = analyze_pending_emails(app_config={"AI_PROVIDER": "rule_based"})
        insight = EmailInsight.query.first()
        item = LifeItem.query.filter(LifeItem.source_key.like("email:%")).first()
        relation = LifeItemRelation.query.filter_by(source_item_id=item.id, target_item_id=existing.id).first()

        self.assertEqual(result["analyzed"], 1)
        self.assertEqual(insight.category, "internship")
        self.assertEqual(insight.priority, "high")
        self.assertIn("resume", json.loads(insight.required_documents_json))
        self.assertIn("transcript", json.loads(insight.required_documents_json))
        self.assertIn("Riya Sharma", json.loads(insight.people_json))
        self.assertIn("https://github.com/anura/flightiq", json.loads(insight.repositories_json))
        self.assertTrue(json.loads(insight.suggested_actions_json))
        self.assertEqual(insight.life_item_id, item.id)
        self.assertEqual(item.category, "internship")
        self.assertEqual(item.repository, "https://github.com/anura/flightiq")
        self.assertIsNotNone(item.deadline)
        self.assertIn("Collect required documents", item.next_action)
        self.assertIsNotNone(relation)
        self.assertEqual(relation.relation_type, "email_context")

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

    def test_existing_sqlite_database_gets_email_life_item_columns(self):
        with tempfile.TemporaryDirectory() as legacy_dir:
            database_path = Path(legacy_dir) / "legacy.db"
            connection = sqlite3.connect(database_path)
            connection.execute("CREATE TABLE reminder (id INTEGER PRIMARY KEY, title VARCHAR(180), due_at DATETIME)")
            connection.execute("CREATE TABLE email_insight (id INTEGER PRIMARY KEY, email_id INTEGER NOT NULL UNIQUE)")
            connection.commit()
            connection.close()

            class LegacyConfig:
                TESTING = True
                SECRET_KEY = "test-secret"
                SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
                SQLALCHEMY_TRACK_MODIFICATIONS = False
                USER_DISPLAY_NAME = "Legacy User"

            legacy_app = create_app(LegacyConfig)
            with legacy_app.app_context():
                columns = {column["name"] for column in db.inspect(db.engine).get_columns("email_insight")}
                self.assertIn("life_item_id", columns)
                self.assertIn("required_documents_json", columns)
                self.assertIn("repositories_json", columns)
                self.assertIn("suggested_actions_json", columns)
                self.assertIn("life_item", db.inspect(db.engine).get_table_names())
                self.assertIn("life_item_relation", db.inspect(db.engine).get_table_names())
                db.session.remove()
                db.engine.dispose()

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

    def test_learning_intelligence_tracks_items_prompts_and_reschedules(self):
        project = LifeItem(
            source_key="manual:rag-project",
            title="RAG Demo",
            description="Project using attention and vector search knowledge.",
            category="project",
            priority="high",
            tags_json=json.dumps(["RAG Demo"]),
        )
        db.session.add(project)
        db.session.commit()

        item_types = ["course", "video", "book", "article", "practice", "project"]
        created = []
        for item_type in item_types:
            created.append(
                upsert_learning_item(
                    {
                        "item_type": item_type,
                        "title": f"{item_type.title()} on attention",
                        "project": "RAG Demo",
                        "completion": 0.25 if item_type == "video" else 0,
                        "scheduled_at": (datetime.utcnow() - timedelta(days=1)).isoformat() if item_type == "video" else None,
                        "notes": "Initial notes",
                        "weak_topics": ["attention math"] if item_type == "course" else [],
                        "projects": ["RAG Demo"],
                        "quiz": ["Explain attention scores"],
                    }
                )["item"]
            )

        summary = learning_summary()
        video = LearningItem.query.filter_by(item_type="video").first()
        event = PlanningEvent.query.filter_by(source_key=f"learning_item:{video.id}").first()
        relation = LifeItemRelation.query.filter_by(
            source_item_id=video.life_item_id,
            target_item_id=project.id,
            relation_type="uses_learning",
        ).first()

        self.assertEqual(summary["counts"]["total"], 6)
        self.assertEqual(summary["counts"]["courses"], 1)
        self.assertEqual(summary["counts"]["videos"], 1)
        self.assertEqual(summary["counts"]["books"], 1)
        self.assertEqual(summary["counts"]["articles"], 1)
        self.assertEqual(summary["counts"]["practice"], 1)
        self.assertEqual(summary["counts"]["projects"], 1)
        self.assertGreater(video.scheduled_at, datetime.utcnow())
        self.assertEqual(event.event_type, "learning_video")
        self.assertIn("Which videos did you complete", event.next_question)
        self.assertTrue(any("Which videos did you complete" in question for question in evening_questions()))
        self.assertIsNotNone(video.life_item_id)
        self.assertIsNotNone(relation)

        update = update_event_progress(
            event.id,
            {
                "status": "in_progress",
                "progress_note": "Completed transformer intro. weak: attention math, masking. quiz: derive QK scores. project: RAG Demo",
            },
        )
        refreshed = db.session.get(LearningItem, video.id)

        self.assertTrue(update["ok"])
        self.assertGreater(refreshed.completion, 0.25)
        self.assertIn("transformer intro", refreshed.notes)
        self.assertIn("attention math", json.loads(refreshed.weak_topics_json))
        self.assertIn("derive QK scores", json.loads(refreshed.quiz_json))
        self.assertIn("RAG Demo", json.loads(refreshed.projects_json))
        self.assertEqual(refreshed.life_item.next_action, "Review weak topics: attention math, masking.")

    def test_learning_progress_completion_updates_life_item_and_plan(self):
        result = upsert_learning_item(
            {
                "item_type": "book",
                "title": "Designing Data Intensive Applications",
                "completion": 0.6,
                "notes": "Read storage chapters",
            }
        )
        item_id = result["item"]["id"]

        progress = record_learning_progress(
            item_id,
            {
                "completed": True,
                "notes": "Finished replication chapter. revise: consensus",
                "weak_topics": ["consensus"],
                "projects": ["AiOS memory"],
            },
        )
        item = db.session.get(LearningItem, item_id)
        event = PlanningEvent.query.filter_by(source_key=f"learning_item:{item_id}").first()

        self.assertTrue(progress["ok"])
        self.assertEqual(item.status, "completed")
        self.assertEqual(item.completion, 1.0)
        self.assertEqual(item.life_item.status, "completed")
        self.assertEqual(item.life_item.progress, 100)
        self.assertIn("consensus", json.loads(item.weak_topics_json))
        self.assertEqual(event.status, "completed")
        self.assertIn("Schedule revision", event.work_left)

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

    def test_daily_assistant_morning_evening_replans_and_preserves_history(self):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        first = PlanningEvent(
            source_key="manual:assistant-finish",
            event_type="repo",
            source="manual",
            title="Ship assistant planner",
            project="AiOS",
            deadline=datetime.combine(today, time(17)),
            planned_start=datetime.combine(today, time(10)),
            planned_minutes=90,
            priority="high",
            status="planned",
            work_left="Finish morning schedule.",
        )
        blocked = PlanningEvent(
            source_key="manual:assistant-blocked",
            event_type="learning",
            source="manual",
            title="Study scheduling risks",
            project="AiOS",
            deadline=datetime.combine(today, time(18)),
            planned_start=datetime.combine(today, time(13)),
            planned_minutes=60,
            priority="normal",
            status="planned",
            work_left="Review risk model.",
        )
        unscheduled_due = PlanningEvent(
            source_key="manual:assistant-risk",
            event_type="email",
            source="manual",
            title="Reply to urgent sponsor",
            project="Email",
            deadline=datetime.combine(tomorrow, time(11)),
            planned_minutes=30,
            priority="urgent",
            status="planned",
            work_left="Send update.",
        )
        db.session.add_all([first, blocked, unscheduled_due])
        db.session.commit()

        morning = generate_morning_briefing(today)
        prompt = evening_checkin_prompt(today)
        response = submit_evening_checkin(
            {
                "date": today.isoformat(),
                "completed": [first.id],
                "blocked": [blocked.id],
                "blockers": "Need clearer priority from user.",
                "hours_worked": 3.5,
                "move_deadlines": {str(blocked.id): tomorrow.isoformat()},
                "modify_priorities": {str(blocked.id): "high"},
                "notes": "Finished planner shell and risk summary.",
            }
        )
        refreshed_first = db.session.get(PlanningEvent, first.id)
        refreshed_blocked = db.session.get(PlanningEvent, blocked.id)
        entries = DailyAssistantEntry.query.order_by(DailyAssistantEntry.created_at.asc()).all()

        self.assertEqual(morning["kind"], "morning")
        self.assertGreaterEqual(len(morning["schedule"]), 2)
        self.assertGreater(morning["estimated_hours"], 0)
        self.assertTrue(any(item["event_id"] == first.id and "high priority" in item["why"] for item in morning["explanations"]))
        self.assertTrue(any("due soon" in item["risk"] or "overdue" in item["risk"] for item in morning["risks"]))
        self.assertIn("What did you complete?", prompt["questions"])
        self.assertTrue(response["ok"])
        self.assertEqual(refreshed_first.status, "completed")
        self.assertEqual(refreshed_blocked.status, "blocked")
        self.assertEqual(refreshed_blocked.priority, "high")
        self.assertEqual(refreshed_blocked.deadline.date(), tomorrow)
        blocked_metadata = json.loads(refreshed_blocked.metadata_json)
        self.assertIn("assistant_history", blocked_metadata)
        self.assertIn("Need clearer priority", blocked_metadata["progress_log"][-1]["note"])
        self.assertGreaterEqual(len(entries), 4)
        self.assertEqual(entries[-1].kind, "evening_response")
        self.assertIn("Finished planner shell", entries[-1].responses_json)
        self.assertTrue(response["next_morning"]["schedule"])

    def test_daily_assistant_api_surfaces_morning_and_evening(self):
        db.session.add(
            PlanningEvent(
                source_key="manual:assistant-api",
                event_type="goal",
                source="manual",
                title="API assistant task",
                planned_start=datetime.combine(date.today(), time(9)),
                planned_minutes=45,
                priority="normal",
                status="planned",
            )
        )
        db.session.commit()

        morning = self.client.post(
            "/api/intelligence/morning",
            headers={"X-AiOS-Token": "local-test-token"},
            json={"date": date.today().isoformat()},
        )
        evening = self.client.get(
            "/api/intelligence/evening",
            headers={"X-AiOS-Token": "local-test-token"},
        )
        submit = self.client.post(
            "/api/intelligence/evening",
            headers={"X-AiOS-Token": "local-test-token"},
            json={"completed": "API assistant task", "hours_worked": 1, "notes": "Done through API."},
        )

        self.assertEqual(morning.status_code, 200)
        self.assertTrue(morning.get_json()["assistant"]["schedule"])
        self.assertEqual(evening.status_code, 200)
        self.assertIn("Hours worked?", evening.get_json()["assistant"]["questions"])
        self.assertEqual(submit.status_code, 200)
        self.assertTrue(submit.get_json()["ok"])
        self.assertEqual(PlanningEvent.query.filter_by(title="API assistant task").first().status, "completed")

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

    def test_github_token_is_used_for_repo_intelligence_refresh(self):
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
                if self.url.endswith("/repos/example/private-repo"):
                    return (
                        b'{"full_name":"example/private-repo","html_url":"https://github.com/example/private-repo",'
                        b'"description":"Private planner repo","default_branch":"main","language":"Python",'
                        b'"private":true,"archived":false,"pushed_at":"2026-07-10T12:00:00Z"}'
                    )
                if "graphql" in self.url:
                    return (
                        b'{"data":{"repository":{"discussions":{"nodes":[{"title":"Roadmap","url":"https://github.com/example/private-repo/discussions/1",'
                        b'"createdAt":"2026-07-08T10:00:00Z","updatedAt":"2026-07-10T10:00:00Z","answerChosenAt":null}]}}}}'
                    )
                if "commits" in self.url:
                    return (
                        b'[{"sha":"abc123456789","html_url":"https://github.com/example/private-repo/commit/abc",'
                        b'"commit":{"message":"ship private planner","author":{"name":"Anura","date":"2026-07-10T10:00:00Z"},'
                        b'"committer":{"date":"2026-07-10T10:00:00Z"}}},'
                        b'{"sha":"def123456789","commit":{"message":"add repo notes","author":{"name":"Anura","date":"2026-07-09T10:00:00Z"},'
                        b'"committer":{"date":"2026-07-09T10:00:00Z"}}}]'
                    )
                if "pulls" in self.url:
                    return (
                        b'[{"number":7,"title":"Polish dashboard","state":"open","created_at":"2026-07-09T10:00:00Z",'
                        b'"updated_at":"2026-07-10T10:00:00Z","html_url":"https://github.com/example/private-repo/pull/7","labels":[]}]'
                    )
                if "issues" in self.url:
                    return (
                        b'[{"number":4,"title":"Add repo notes","state":"open","created_at":"2026-07-08T10:00:00Z",'
                        b'"updated_at":"2026-07-10T10:00:00Z","html_url":"https://github.com/example/private-repo/issues/4",'
                        b'"labels":[{"name":"todo"}]},'
                        b'{"number":3,"title":"Closed setup","state":"closed","created_at":"2026-07-07T10:00:00Z",'
                        b'"updated_at":"2026-07-08T10:00:00Z","closed_at":"2026-07-08T10:00:00Z","html_url":"https://github.com/example/private-repo/issues/3",'
                        b'"labels":[]}]'
                    )
                if "branches" in self.url:
                    return b'[{"name":"main","protected":true},{"name":"feature/planner","protected":false}]'
                if "releases" in self.url:
                    return b'[{"name":"v0.1","tag_name":"v0.1","published_at":"2026-07-08T10:00:00Z","draft":false,"prerelease":false}]'
                if "actions/workflows" in self.url:
                    return b'{"workflows":[{"name":"Tests","state":"active","path":".github/workflows/test.yml","html_url":"https://github.com/example/private-repo/actions"}]}'
                if "contributors" in self.url:
                    return b'[{"login":"anura","contributions":12,"html_url":"https://github.com/anura"}]'
                return b"{}"

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

        self.assertTrue(all(value == "Bearer ghp_local_test" for value in captured["authorization"]))
        self.assertGreaterEqual(len(captured["urls"]), 9)
        self.assertIn("ship private planner", event.repo_latest_activity)
        self.assertIn("1 issues, 1 PRs", event.repo_latest_activity)
        self.assertIn("Completion estimate", event.repo_latest_activity)

        repo = GitHubRepository.query.filter_by(repo_full_name="example/private-repo").first()
        self.assertIsNotNone(repo)
        self.assertIsNotNone(repo.life_item_id)
        self.assertFalse(repo.inactive)
        self.assertGreater(repo.completion_percentage, 0)
        self.assertIn("Polish dashboard", repo.current_sprint)
        self.assertIn("Add repo notes", repo.remaining_work)
        self.assertIn("Review or merge PR #7", repo.suggested_next_task)
        self.assertEqual(len(json.loads(repo.branches_json)), 2)
        self.assertEqual(len(json.loads(repo.releases_json)), 1)
        self.assertEqual(len(json.loads(repo.discussions_json)), 1)
        self.assertEqual(len(json.loads(repo.workflows_json)), 1)
        self.assertEqual(len(json.loads(repo.contributors_json)), 1)

    def test_github_intelligence_updates_all_repositories_and_daily_summary(self):
        item = LifeItem(
            source_key="manual:stale-repo",
            title="Stale repo",
            category="project",
            repository="https://github.com/example/stale-repo",
        )
        db.session.add(item)
        db.session.commit()

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                if self.url.endswith("/repos/example/stale-repo"):
                    return (
                        b'{"full_name":"example/stale-repo","html_url":"https://github.com/example/stale-repo",'
                        b'"description":"Old project","default_branch":"main","language":"JavaScript",'
                        b'"private":false,"archived":false,"pushed_at":"2026-01-01T12:00:00Z"}'
                    )
                if "graphql" in self.url:
                    return b'{"data":{"repository":{"discussions":{"nodes":[]}}}}'
                if "commits" in self.url:
                    return b'[{"sha":"aaa111","commit":{"message":"initial app","author":{"name":"Anura","date":"2026-01-01T10:00:00Z"},"committer":{"date":"2026-01-01T10:00:00Z"}}}]'
                if "pulls" in self.url:
                    return b"[]"
                if "issues" in self.url:
                    return b'[{"number":9,"title":"Finish README","state":"open","updated_at":"2026-01-02T10:00:00Z","labels":[]}]'
                if "branches" in self.url:
                    return b'[{"name":"main","protected":false}]'
                if "releases" in self.url:
                    return b"[]"
                if "actions/workflows" in self.url:
                    return b'{"workflows":[]}'
                if "contributors" in self.url:
                    return b'[{"login":"anura","contributions":1}]'
                return b"{}"

        def fake_urlopen(request, timeout):
            FakeResponse.url = request.full_url
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = update_all_repositories()

        repo = GitHubRepository.query.filter_by(repo_full_name="example/stale-repo").first()
        daily = GitHubDailySummary.query.filter_by(summary_date=date.today()).first()

        self.assertTrue(result["ok"])
        self.assertTrue(repo.inactive)
        self.assertEqual(repo.life_item_id, item.id)
        self.assertEqual(item.next_action, "Work on issue #9: Finish README")
        self.assertEqual(item.progress, repo.completion_percentage)
        self.assertEqual(daily.repo_count, 1)
        self.assertEqual(daily.inactive_count, 1)
        self.assertIn("inactive projects", daily.summary)
        self.assertIn("Finish README", json.loads(daily.suggested_tasks_json)[0])

    def test_knowledge_graph_answers_continue_project_from_connected_context(self):
        account = ConnectedAccount(provider="google", email="me@example.com", label="Main")
        life = LifeItem(
            source_key="manual:flightiq",
            title="FlightIQ",
            description="Hackathon flight intelligence dashboard.",
            category="hackathon",
            priority="high",
            status="open",
            repository="https://github.com/anura/flightiq",
            next_action="Record demo video",
            tags_json=json.dumps(["FlightIQ", "Amazon"]),
        )
        repo = GitHubRepository(
            repo_full_name="anura/flightiq",
            html_url="https://github.com/anura/flightiq",
            life_item=life,
            current_sprint="Demo milestone: finish charts and submit video",
            remaining_work="Open issues: add repo notes; export dashboard",
            recent_progress="Recent commits: 2026-07-10 polish dashboard | 2026-07-09 add repo notes",
            suggested_next_task="Record demo video and close issue #4",
            completion_percentage=72,
            commits_json=json.dumps(
                [
                    {"sha": "abc123", "message": "polish dashboard", "date": "2026-07-10T10:00:00Z"},
                    {"sha": "def456", "message": "add repo notes", "date": "2026-07-09T10:00:00Z"},
                ]
            ),
            issues_json=json.dumps([{"number": 4, "title": "Add repo notes", "state": "open"}]),
            pull_requests_json=json.dumps([]),
        )
        email = EmailMessage(
            account=account,
            provider_message_id="flightiq-email",
            sender='"Riya Sharma" <riya@amazon.com>',
            subject="FlightIQ hackathon deadline and meeting",
            snippet="Please submit FlightIQ by Friday and join the review call.",
            body_text="Amazon needs FlightIQ by Friday. Riya will join the meeting.",
            labels_json=json.dumps(["INBOX", "IMPORTANT"]),
            sent_at=datetime(2026, 7, 10, 9, 0),
        )
        db.session.add_all([account, life, repo, email])
        db.session.flush()
        hackathon = Opportunity(
            kind="hackathon",
            title="FlightIQ Challenge",
            organization="Build Club",
            status="Tracked",
            source="https://devpost.example/flightiq",
            deadline=datetime(2026, 7, 13, 17),
            notes="Submit FlightIQ demo and final repository.",
        )
        insight = EmailInsight(
            email=email,
            life_item=life,
            priority="high",
            urgency="urgent",
            category="hackathon",
            summary="Amazon asked for FlightIQ submission by Friday.",
            action_items_json=json.dumps(["Submit FlightIQ"]),
            deadlines_json=json.dumps(["by Friday"]),
            meetings_json=json.dumps(["FlightIQ review call"]),
            projects_json=json.dumps(["FlightIQ"]),
            people_json=json.dumps(["Riya Sharma"]),
            companies_json=json.dumps(["Amazon"]),
            suggested_actions_json=json.dumps(["Submit demo"]),
        )
        learning = LearningItem(
            life_item=life,
            item_type="video",
            title="RAG dashboard video for FlightIQ",
            project="FlightIQ",
            completion=0.5,
            notes="Need to revise chart explanations.",
            weak_topics_json=json.dumps(["dashboard storytelling"]),
            projects_json=json.dumps(["FlightIQ"]),
        )
        meeting = PlanningEvent(
            source_key="calendar:flightiq-review",
            event_type="meeting",
            source="calendar",
            title="FlightIQ review meeting",
            project="FlightIQ",
            deadline=datetime(2026, 7, 12, 17),
            planned_start=datetime(2026, 7, 12, 11),
            planned_minutes=45,
            status="planned",
            work_left="Prepare review notes.",
        )
        project_memory = MemoryEntity(
            entity_type="project",
            name="FlightIQ",
            slug="project-flightiq",
            summary="FlightIQ hackathon project with dashboard and demo.",
        )
        goal = MemoryEntity(entity_type="goal", name="Ship FlightIQ", slug="goal-ship-flightiq", summary="Submit FlightIQ demo.")
        db.session.add_all([hackathon, insight, learning, meeting, project_memory, goal])
        db.session.flush()
        checkpoint = WorkCheckpoint(
            project=project_memory,
            summary="Charts are working.",
            active_tasks_json=json.dumps(["Record demo video"]),
            next_actions_json=json.dumps(["Submit final link"]),
            notes="Latest note: dashboard polish is done.",
        )
        fact = MemoryFact(entity=project_memory, fact_type="note", content="FlightIQ notes: demo script needs cleanup.", source="manual")
        plan = GoalPlan(goal=goal, title="FlightIQ final sprint", cadence="daily", status="active", strategy="Finish demo then submit.")
        task = PlanTask(plan=plan, title="Submit FlightIQ milestone", status="in_progress", suggested_next="Upload demo video")
        db.session.add_all([checkpoint, fact, plan, task])
        db.session.flush()
        db.session.add(LifeItemRelation(source_item=life, target_item=life, relation_type="self_skip"))  # ignored by graph edge guard
        db.session.commit()

        graph = build_knowledge_graph()
        result = query_knowledge_graph("Continue FlightIQ")
        answer = result["answer"]

        self.assertGreaterEqual(len(graph["nodes"]), 10)
        self.assertTrue(any(node["kind"] == "repository" and node["title"] == "anura/flightiq" for node in result["nodes"]))
        self.assertTrue(any(node["kind"] == "hackathon" and node["title"] == "FlightIQ Challenge" for node in result["nodes"]))
        self.assertIn("polish dashboard", answer["latest_commits"][0]["message"])
        self.assertIn("Demo milestone", answer["current_milestone"])
        self.assertTrue(any("FlightIQ hackathon deadline" in item["title"] for item in answer["emails"]))
        self.assertTrue(any("demo script" in item["data"].get("content", "") or "dashboard polish" in item["data"].get("notes", "") for item in answer["notes"]))
        self.assertTrue(any(item["deadline"] for item in answer["deadlines"]))
        self.assertTrue(any("RAG dashboard video" in item["title"] for item in answer["related_learning"]))
        self.assertTrue(any("FlightIQ review meeting" in item["title"] for item in answer["meetings"]))
        self.assertTrue(any("Riya Sharma" == item["title"] for item in answer["people"]))
        self.assertTrue(any("Amazon" == item["title"] for item in answer["companies"]))
        self.assertIn("Record demo video", answer["next_action"])

        response = self.client.get(
            "/api/knowledge-graph/query",
            headers={"X-AiOS-Token": "local-test-token"},
            query_string={"q": "Continue FlightIQ"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])
        self.assertIn("latest_commits", response.get_json()["answer"])

    def test_email_sync_interval_is_configurable_with_safe_floor(self):
        set_setting("EMAIL_SYNC_INTERVAL_MINUTES", "1")
        db.session.commit()
        self.assertEqual(sync_interval_seconds(self.app), 120)

        set_setting("EMAIL_SYNC_INTERVAL_MINUTES", "7")
        db.session.commit()
        self.assertEqual(sync_interval_seconds(self.app), 420)


if __name__ == "__main__":
    unittest.main()
