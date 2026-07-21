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
    InboxItem,
    EmailThread,
    LearningItem,
    LifeItem,
    LifeItemRelation,
    MemoryEntity,
    MemoryFact,
    Opportunity,
    OAuthToken,
    PlacementUpdate,
    PlanTask,
    GoalPlan,
    PlanningEvent,
    Reminder,
    WorkCheckpoint,
    db,
)
from app.services.email_intelligence import (
    _gmail_message_ids,
    analyze_pending_emails,
    decrypt_token_json,
    encrypt_token_json,
    generate_daily_plan,
    google_client_status,
    intelligence_summary,
    run_email_intelligence_cycle,
    sync_account,
    upsert_gmail_message,
    upsert_email_insight,
)
from app.services.college_intelligence import pat_college_summary
from app.services.email_views import latest_email_ids_per_account, materialize_email_views
from app.services.application_intelligence import application_overview
from app.routes import build_dashboard_context
from app.services.project_context import create_project, project_context, update_project
from app.services.github_intelligence import update_all_repositories, update_repository
from app.services.learning_intelligence import evening_questions, learning_summary, record_learning_progress, upsert_learning_item
from app.services.daily_assistant import (
    evening_checkin_prompt,
    generate_morning_briefing,
    run_daily_assistant_cycle,
    submit_evening_checkin,
)
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

        self.config_class = TestConfig
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

    def test_sync_error_is_safe_helpful_and_preserves_account(self):
        account = ConnectedAccount(provider="google", email="still-here@example.com", label="Still here")
        db.session.add(account)
        db.session.commit()

        with mock.patch(
            "app.services.email_intelligence.credentials_for_account",
            side_effect=RuntimeError("invalid_grant: Token has been expired or revoked"),
        ):
            result = sync_account(account)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "google_access_expired")
        self.assertIn("still saved", result["message"])
        self.assertIn("connect it again", result["suggested_fix"])
        self.assertIsNotNone(db.session.get(ConnectedAccount, account.id))

    def test_gmail_insights_feed_inbox_opportunities_and_reminders(self):
        account = ConnectedAccount(provider="google", email="student@example.com", label="Student")
        email = EmailMessage(
            account=account,
            provider_message_id="opportunity-1",
            sender="recruiting@example.org",
            subject="Backend internship interview by Friday",
            snippet="Please prepare for the interview by Friday.",
            body_text="Action required: prepare for the backend internship interview by Friday.",
            is_unread=True,
            sent_at=datetime.now(),
        )
        db.session.add_all([account, email])
        db.session.flush()
        upsert_email_insight(
            email,
            {
                "priority": "high",
                "urgency": "urgent",
                "category": "internship",
                "summary": "Backend internship interview requires preparation.",
                "action_items": ["Prepare for backend interview"],
                "deadlines": ["by Friday"],
                "meetings": ["Backend interview"],
                "follow_ups": [],
                "waiting_on": [],
                "projects": ["Backend internship"],
                "people": [],
                "companies": ["Example"],
                "required_documents": ["resume"],
                "repositories": [],
                "suggested_actions": ["Review interview requirements"],
                "confidence": 0.91,
            },
        )
        db.session.commit()

        result = materialize_email_views()

        self.assertTrue(result["ok"])
        self.assertEqual(InboxItem.query.filter_by(email_message_id=email.id).count(), 1)
        self.assertEqual(Opportunity.query.filter_by(email_message_id=email.id).count(), 1)
        self.assertEqual(Reminder.query.filter(Reminder.source_key.like("email-task:%")).count(), 0)
        materialize_email_views()
        self.assertEqual(InboxItem.query.filter_by(email_message_id=email.id).count(), 1)

    def test_round_selection_and_promptwars_deadline_become_highlights(self):
        account = ConnectedAccount(provider="google", email="builder@example.com", label="Builder")
        email = EmailMessage(
            account=account,
            provider_message_id="promptwars-round-2",
            sender="PromptWars <admin@hack2skill.com>",
            subject="You have been selected for Round 2 of PromptWars",
            snippet="Congratulations. Build your Challenge 4 project and submit it by Sunday.",
            body_text=(
                "You have been selected for Round 2. The final week is live. "
                "Build your Challenge 4 project and submit it by Sunday before the rush."
            ),
            sent_at=datetime(2026, 7, 15, 9, 0),
        )
        db.session.add_all([account, email])
        db.session.flush()
        upsert_email_insight(
            email,
            {
                "priority": "high",
                "urgency": "urgent",
                "category": "hackathon",
                "summary": "PromptWars selected you for the second round.",
                "action_items": ["Build and submit Challenge 4"],
                "deadlines": [],
                "meetings": [],
                "follow_ups": [],
                "waiting_on": [],
                "projects": ["PromptWars"],
                "people": [],
                "companies": ["PromptWars"],
                "required_documents": [],
                "repositories": [],
                "suggested_actions": ["Finish the PromptWars project"],
                "confidence": 0.94,
            },
        )
        db.session.commit()

        materialize_email_views()
        opportunity = Opportunity.query.filter_by(email_message_id=email.id).one()
        inbox = InboxItem.query.filter_by(email_message_id=email.id).one()

        self.assertEqual(opportunity.status, "Selected for Round 2")
        self.assertEqual(opportunity.deadline, datetime(2026, 7, 19, 18, 0))
        self.assertGreaterEqual(len(inbox.summary.splitlines()), 3)
        self.assertLessEqual(len(inbox.summary.splitlines()), 4)

    def test_general_mail_with_personal_next_round_language_is_an_achievement(self):
        account = ConnectedAccount(provider="google", email="grid@example.com", label="Grid")
        email = EmailMessage(
            account=account,
            provider_message_id="grid-round-1",
            sender="Flipkart <admin@hirepro.in>",
            subject="Flipkart GRiD 8.0 | Round 1 (Screening) Update",
            snippet=(
                "We are pleased to inform you that your profile is eligible for the next "
                "round of evaluation. Hearty Congratulations!"
            ),
            sent_at=datetime.now(),
        )
        db.session.add_all([account, email])
        db.session.flush()
        upsert_email_insight(
            email,
            {
                "priority": "normal",
                "urgency": "normal",
                "category": "general",
                "summary": email.snippet,
                "action_items": [],
                "deadlines": [],
                "meetings": [],
                "follow_ups": [],
                "waiting_on": [],
                "projects": [],
                "people": [],
                "companies": ["Flipkart"],
                "required_documents": [],
                "repositories": [],
                "suggested_actions": [],
                "confidence": 0.8,
            },
        )
        db.session.commit()

        materialize_email_views()
        opportunity = Opportunity.query.filter_by(email_message_id=email.id).one()

        self.assertEqual(opportunity.status, "Selected for Round 2")
        self.assertEqual(opportunity.kind, "competition")

    def test_today_reminders_only_use_latest_one_hundred_emails(self):
        account = ConnectedAccount(provider="google", email="tasks@example.com", label="Tasks")
        db.session.add(account)
        db.session.flush()
        anchor = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        emails = []
        for index in range(101):
            email = EmailMessage(
                account=account,
                provider_message_id=f"task-mail-{index}",
                sender="tasks@example.com",
                subject=f"Task mail {index}",
                snippet="A task update.",
                sent_at=anchor - timedelta(minutes=index),
            )
            emails.append(email)
            db.session.add(email)
        db.session.flush()
        db.session.add_all(
            [
                EmailTask(email=emails[0], title="Do this today", priority="high", due_at=None),
                EmailTask(email=emails[1], title="Do this tomorrow", priority="high", due_at=anchor + timedelta(days=1)),
                EmailTask(email=emails[100], title="Old mail task", priority="urgent", due_at=anchor),
            ]
        )
        db.session.commit()

        result = materialize_email_views(limit=250)
        reminders = Reminder.query.filter(Reminder.source_key.like("email-task:%")).all()

        self.assertEqual(result["emails_scanned"], 100)
        self.assertEqual([item.title for item in reminders], ["Do this today"])
        self.assertEqual(reminders[0].due_at.date(), date.today())

    def test_latest_one_hundred_emails_are_scanned_for_each_connected_account(self):
        first = ConnectedAccount(provider="google", email="first@example.com", label="First")
        second = ConnectedAccount(provider="google", email="second@example.com", label="Second")
        db.session.add_all([first, second])
        db.session.flush()
        anchor = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        newest = []
        oldest = []
        for account in (first, second):
            rows = []
            for index in range(101):
                email = EmailMessage(
                    account=account,
                    provider_message_id=f"{account.id}-mail-{index}",
                    sender=account.email,
                    subject=f"{account.label} mail {index}",
                    snippet="A local email update.",
                    sent_at=anchor - timedelta(minutes=index),
                )
                rows.append(email)
                db.session.add(email)
            newest.append(rows[0])
            oldest.append(rows[-1])
        db.session.flush()
        for index, email in enumerate(newest):
            db.session.add(
                EmailTask(
                    email=email,
                    title=f"Account task {index}",
                    priority="urgent",
                )
            )
        for index, email in enumerate(oldest):
            db.session.add(
                EmailTask(
                    email=email,
                    title=f"Old excluded task {index}",
                    priority="urgent",
                )
            )
        db.session.commit()

        result = materialize_email_views(limit=100)
        reminder_titles = {
            item.title
            for item in Reminder.query.filter(
                Reminder.notification_type == "email_action"
            ).all()
        }

        self.assertEqual(result["emails_scanned"], 200)
        self.assertEqual(result["accounts_scanned"], 2)
        self.assertEqual(result["per_account_limit"], 100)
        self.assertEqual(len(latest_email_ids_per_account()), 200)
        self.assertEqual(reminder_titles, {"Account task 0", "Account task 1"})

    def test_dashboard_reminders_and_stats_only_use_recent_email_actions(self):
        account = ConnectedAccount(provider="google", email="scope@example.com", label="Scope")
        email = EmailMessage(
            account=account,
            provider_message_id="scope-message",
            sender="team@example.com",
            subject="Submit the project update",
            snippet="Please submit today.",
            sent_at=datetime.now(),
        )
        db.session.add_all([account, email])
        db.session.flush()
        db.session.add(
            EmailTask(
                email=email,
                title="Submit project update",
                priority="urgent",
            )
        )
        db.session.add(
            Reminder(
                source_key="daily-review:test",
                title="Daily Review",
                due_at=datetime.now(),
                notification_type="daily_review",
            )
        )
        db.session.commit()
        materialize_email_views(limit=100)

        with self.app.test_request_context("/"):
            context = build_dashboard_context()

        self.assertEqual([item.title for item in context["reminders"]], ["Submit project update"])
        self.assertEqual(context["stats"]["active_reminders"], 1)

    def test_pat_college_summary_extracts_today_class_and_requirements(self):
        account = ConnectedAccount(provider="google", email="college@example.com", label="College")
        email = EmailMessage(
            account=account,
            provider_message_id="pat-1",
            sender="pat@vitbhopal.ac.in",
            subject="PAT class today",
            snippet="PAT class today at 10:30 am.",
            body_text="PAT class today at 10:30 am. Venue: Lab 2. Bring laptop and college ID card. Attendance is mandatory.",
            sent_at=datetime.now(),
        )
        db.session.add_all([account, email])
        db.session.commit()

        summary = pat_college_summary()

        self.assertTrue(summary["has_class_today"])
        self.assertEqual(summary["status"], "scheduled")
        self.assertEqual(summary["time"], "10:30 am")
        self.assertIn("laptop", summary["bring"])
        self.assertIn("college ID card", summary["bring"])
        self.assertIn("Lab 2", summary["location"])

    def test_pat_college_summary_ignores_job_mail_and_quoted_timestamps(self):
        account = ConnectedAccount(provider="google", email="college@example.com", label="College")
        anchor = datetime(2026, 7, 15, 10, 0)
        exam = EmailMessage(
            account=account,
            provider_message_id="pat-exam",
            sender="pat@vitbhopal.ac.in",
            subject="PAT exam on Friday + ID card",
            snippet="Bring your laptop and college ID card for the PAT exam.",
            body_text=(
                "Bring your laptop, college ID card, 10th marksheet and rough sheets. "
                "Report at 9 am.\nOn Tue, Jul 14, 2026 at 6:08 PM Placement Office &lt;"
                + ("long-address-fragment" * 12)
                + "&gt; wrote: class today."
            ),
            sent_at=anchor,
        )
        job = EmailMessage(
            account=account,
            provider_message_id="pat-job",
            sender="placement@example.com",
            subject="Fwd: Example Corp Super Dream Offer (Internship + Full Time) Registration - 2027 Batch",
            snippet="Only students enrolled in PAT can apply.",
            body_text="Date of Visit: later. Internship registration for PAT students.",
            sent_at=anchor,
        )
        db.session.add_all([account, exam, job])
        db.session.commit()

        summary = pat_college_summary(today=date(2026, 7, 15))

        self.assertFalse(summary["has_class_today"])
        self.assertEqual(summary["status"], "upcoming")
        self.assertEqual(len(summary["updates"]), 1)
        self.assertEqual(summary["next_event_days"], 2)
        self.assertIn("Friday, 17 Jul", summary["headline"])
        self.assertEqual(summary["updates"][0]["event_date"], "2026-07-17")
        self.assertEqual(summary["updates"][0]["time"], "9 am")
        self.assertEqual(summary["updates"][0]["location"], "")
        self.assertIn("10th marksheet", summary["updates"][0]["bring"])
        self.assertIn("rough sheets", summary["updates"][0]["bring"])
        self.assertIn("10th marksheet", summary["bring"])
        self.assertGreaterEqual(len(summary["latest_summary"].splitlines()), 3)

    def test_project_context_keeps_selected_repo_folder_progress_and_timeline(self):
        result = create_project(
            "FlightIQ",
            "https://github.com/anura/flightiq",
            str(Path(self.temp_dir.name) / "flightiq"),
        )
        project_id = result["project"]["id"]
        item = db.session.get(LifeItem, project_id)
        repository = GitHubRepository(
            repo_full_name="anura/flightiq",
            html_url="https://github.com/anura/flightiq",
            life_item=item,
            completion_percentage=64,
            recent_progress="Dashboard and API completed.",
            remaining_work="Finish evaluation and release.",
            suggested_next_task="Run evaluation suite.",
            commits_json=json.dumps([{"date": "2026-07-15T09:00:00", "message": "Add dashboard", "url": "https://github.com/anura/flightiq/commit/1"}]),
        )
        db.session.add(repository)
        db.session.commit()
        update_project(project_id, {"progress": 64, "selected": True, "progress_note": "Dashboard shipped."})

        context = project_context()

        self.assertEqual(context["selected"]["title"], "FlightIQ")
        self.assertEqual(context["selected"]["progress"], 64)
        self.assertIn("flightiq", context["selected"]["working_directory"].lower())

    def test_project_context_falls_back_to_local_git_when_github_is_unavailable(self):
        result = create_project(
            "Local Project",
            "https://github.com/example/local-project",
            str(Path(self.temp_dir.name) / "local-project"),
        )
        local_snapshot = {
            "branch": "main",
            "progress": 40,
            "work_done": "Recent local commits: Build mail intelligence",
            "remaining_work": "2 uncommitted file changes need review on main.",
            "next_action": "Review and commit the 2 local changes.",
            "commits": [
                {
                    "at": "2026-07-15T10:00:00+00:00",
                    "kind": "commit",
                    "title": "Build mail intelligence",
                    "url": "https://github.com/example/local-project/commit/abc",
                }
            ],
        }

        with mock.patch("app.services.project_context._local_git_snapshot", return_value=local_snapshot):
            context = project_context()

        self.assertEqual(context["selected"]["id"], result["project"]["id"])
        self.assertEqual(context["selected"]["progress"], 40)
        self.assertIn("Build mail intelligence", context["selected"]["work_done"])
        self.assertEqual(context["selected"]["next_action"], "Review and commit the 2 local changes.")
        self.assertTrue(any(entry["kind"] == "commit" for entry in context["selected"]["timeline"]))
        self.assertTrue(any(event["kind"] == "commit" for event in context["selected"]["timeline"]))

    def test_project_context_groups_repository_mail_updates_and_hides_merge_commits(self):
        first = LifeItem(
            source_key="email:1:legal-1",
            title="LegalEase pull request update",
            category="project",
            repository="https://github.com/anura/legalease",
        )
        second = LifeItem(
            source_key="email:1:legal-2",
            title="Another LegalEase notification",
            category="project",
            repository="https://github.com/anura/legalease",
        )
        db.session.add_all([first, second])
        db.session.flush()
        db.session.add(
            GitHubRepository(
                repo_full_name="anura/legalease",
                html_url="https://github.com/anura/legalease",
                life_item=first,
                commits_json=json.dumps(
                    [
                        {"date": "2026-07-15T10:00:00", "message": "Merge pull request #42 from feature", "url": "merge"},
                        {"date": "2026-07-15T09:00:00", "message": "Add contract review", "url": "feature"},
                    ]
                ),
            )
        )
        db.session.commit()

        context = project_context()

        self.assertEqual(context["counts"]["total"], 1)
        self.assertEqual(context["projects"][0]["grouped_updates"], 2)
        titles = [event["title"] for event in context["projects"][0]["timeline"]]
        self.assertIn("Add contract review", titles)
        self.assertFalse(any(title.startswith("Merge pull request") for title in titles))

    def test_connected_accounts_and_tokens_survive_app_restart(self):
        account = ConnectedAccount(provider="google", email="persistent@example.com", label="Persistent")
        db.session.add(account)
        db.session.flush()
        db.session.add(
            OAuthToken(
                account=account,
                token_json_encrypted=encrypt_token_json(json.dumps({"refresh_token": "keep-until-disconnected"})),
            )
        )
        db.session.commit()
        account_id = account.id

        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()
        try:
            restarted_app = create_app(self.config_class)
            with restarted_app.app_context():
                persisted = db.session.get(ConnectedAccount, account_id)
                self.assertIsNotNone(persisted)
                self.assertEqual(persisted.email, "persistent@example.com")
                self.assertEqual(
                    json.loads(decrypt_token_json(persisted.oauth_token.token_json_encrypted))["refresh_token"],
                    "keep-until-disconnected",
                )
                db.session.remove()
                db.engine.dispose()
        finally:
            self.ctx = self.app.app_context()
            self.ctx.push()

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
        upcoming_blocks = (
            summary["planning_events"]["plan_blocks"]["week"]
            + summary["planning_events"]["plan_blocks"]["next_week"]
        )
        self.assertGreaterEqual(len(upcoming_blocks), 1)

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

    def test_incremental_history_sync_follows_pages_and_label_changes(self):
        pages = {
            None: {
                "historyId": "220",
                "nextPageToken": "next",
                "history": [{"messagesAdded": [{"message": {"id": "m-1"}}]}],
            },
            "next": {
                "historyId": "240",
                "history": [{"labelsRemoved": [{"message": {"id": "m-2"}}]}],
            },
        }

        class FakeExecute:
            def __init__(self, payload):
                self.payload = payload

            def execute(self):
                return self.payload

        class FakeHistory:
            def list(self, **kwargs):
                return FakeExecute(pages[kwargs.get("pageToken")])

        class FakeUsers:
            def history(self):
                return FakeHistory()

        class FakeService:
            def users(self):
                return FakeUsers()

        account = ConnectedAccount(provider="google", email="pages@example.com", sync_cursor="100")
        self.assertEqual(_gmail_message_ids(FakeService(), account, limit=10), ["m-1", "m-2"])
        self.assertEqual(account.sync_cursor, "240")

    def test_google_desktop_oauth_client_status_hides_client_secret(self):
        target = Path(self.temp_dir.name) / "credentials" / "google_client_secret.json"
        config = {"GMAIL_CREDENTIALS_PATH": str(target)}
        client = {
            "installed": {
                "client_id": "desktop-client.apps.googleusercontent.com",
                "client_secret": "local-client-secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(client), encoding="utf-8")
        status = google_client_status(config)

        self.assertTrue(status["ready"])
        self.assertNotIn("local-client-secret", json.dumps(status))

    def test_removing_account_revokes_google_token_and_deletes_local_data(self):
        account = ConnectedAccount(provider="google", email="remove@example.com", label="Remove")
        db.session.add(account)
        db.session.flush()
        db.session.add(
            OAuthToken(
                account=account,
                token_json_encrypted=encrypt_token_json(json.dumps({"refresh_token": "refresh-secret"})),
            )
        )
        db.session.commit()

        response = mock.MagicMock()
        response.__enter__.return_value.status = 200
        with mock.patch("app.services.email_intelligence.urllib.request.urlopen", return_value=response) as revoke:
            from app.services.email_intelligence import remove_account

            result = remove_account(account.id)

        self.assertTrue(result["revoked"])
        self.assertIsNone(db.session.get(ConnectedAccount, account.id))
        self.assertIn(b"refresh-secret", revoke.call_args.args[0].data)

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
        self.assertIn("Add another Google account", html)
        self.assertIn("Manage", html)
        self.assertNotIn("Sync All Now", html)
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

    def test_google_sign_in_uses_navigation_route_and_returns_to_accounts(self):
        job = {
            "id": "sign-in-test",
            "status": "waiting",
            "message": "Finish choosing your Google account in the browser.",
            "can_continue": True,
            "terminal": False,
            "created_at": "2026-07-15T00:00:00+00:00",
            "updated_at": "2026-07-15T00:00:00+00:00",
        }
        with mock.patch(
            "app.routes._start_google_sign_in",
            return_value=job,
        ) as start:
            response = self.client.get("/settings/google/connect")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/settings/google/sign-in/sign-in-test", response.headers["Location"])
        start.assert_called_once()

        with mock.patch("app.routes.get_google_sign_in", return_value=job):
            wait = self.client.get("/settings/google/sign-in/sign-in-test")
        html = wait.get_data(as_text=True)
        self.assertEqual(wait.status_code, 200)
        self.assertIn("Continue in your browser", html)
        self.assertIn("Cancel sign-in", html)
        self.assertIn('data-google-sign-in-job="sign-in-test"', html)

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
        planned_start = datetime.now() + timedelta(hours=1)
        deadline = planned_start + timedelta(days=2)
        response = self.client.post(
            "/api/planning-events",
            headers={"X-AiOS-Token": "local-test-token"},
            json={
                "event_type": "learning_video",
                "title": "Finish GenAI attention video",
                "project": "GenAI",
                "idea": "Understand attention before building the demo.",
                "deadline": deadline.isoformat(),
                "planned_start": planned_start.isoformat(),
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
        self.assertTrue(
            all(
                datetime.fromisoformat(item["start"]).date() == tomorrow
                for item in response["next_morning"]["schedule"]
            )
        )

    def test_daily_assistant_cycle_runs_once_per_morning_and_evening(self):
        today = date.today()
        db.session.add(
            PlanningEvent(
                source_key="manual:assistant-cycle",
                event_type="goal",
                source="manual",
                title="Cycle assistant task",
                planned_start=datetime.combine(today, time(9)),
                planned_minutes=45,
                priority="normal",
                status="planned",
            )
        )
        db.session.commit()

        morning = run_daily_assistant_cycle(datetime.combine(today, time(8)))
        morning_again = run_daily_assistant_cycle(datetime.combine(today, time(9)))
        evening = run_daily_assistant_cycle(datetime.combine(today, time(19)))
        evening_again = run_daily_assistant_cycle(datetime.combine(today, time(20)))

        self.assertEqual(morning["created"], ["morning"])
        self.assertEqual(morning_again["created"], [])
        self.assertEqual(evening["created"], ["evening_prompt"])
        self.assertEqual(evening_again["created"], [])
        self.assertEqual(DailyAssistantEntry.query.filter_by(entry_date=today, kind="morning").count(), 1)
        self.assertEqual(DailyAssistantEntry.query.filter_by(entry_date=today, kind="evening_prompt").count(), 1)

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
        planned_start = datetime.now() + timedelta(hours=1)
        deadline = planned_start + timedelta(days=2)
        create_manual_event(
            {
                "event_type": "learning_video",
                "title": "Finish GenAI attention video",
                "project": "GenAI",
                "deadline": deadline.isoformat(),
                "planned_start": planned_start.isoformat(),
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

    def test_application_overview_keeps_latest_100_and_archives_the_rest(self):
        account = ConnectedAccount(provider="google", email="career@example.com", label="Career")
        db.session.add(account)
        db.session.flush()
        now = datetime.now()
        for index in range(102):
            email = EmailMessage(
                account=account,
                provider_message_id=f"application-{index}",
                sender="jobs-noreply@linkedin.com",
                subject=f"Thank you for applying to Company {index}",
                snippet="Your application was received.",
                body_text="We received your application through LinkedIn Jobs.",
                sent_at=now - timedelta(days=index),
            )
            db.session.add(email)
            db.session.flush()
            opportunity = Opportunity(
                source_key=f"gmail:{account.id}:{email.provider_message_id}",
                email_message_id=email.id,
                kind="job",
                title=f"Software Intern {index}",
                organization=f"Company {index}",
                status="Applied",
                source="Gmail",
                created_at=email.sent_at,
                updated_at=email.sent_at,
            )
            db.session.add(opportunity)
        db.session.commit()

        result = application_overview()

        self.assertEqual(len(result["active"]), 100)
        self.assertEqual(len(result["archive"]), 2)
        self.assertEqual(result["stats"]["emails_scanned"], 102)
        self.assertEqual(result["active"][0]["platform"], "LinkedIn")
        self.assertEqual(result["active"][0]["source_email"]["account_email"], "career@example.com")
        self.assertTrue(result["archive"][0]["archived"])

        response = self.client.get(
            "/api/applications",
            headers={"X-AiOS-Token": "local-test-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()["active"]), 100)

    def test_planner_prioritizes_hiring_steps_and_low_progress_projects(self):
        account = ConnectedAccount(provider="google", email="jobs@example.com", label="Jobs")
        email = EmailMessage(
            account=account,
            provider_message_id="assessment-today",
            sender="recruiting@linkedin.com",
            subject="Online assessment for Backend Intern",
            snippet="Complete the online assessment tomorrow.",
            body_text="Your application moved to the next round. Complete the online test tomorrow.",
            sent_at=datetime.now(),
        )
        db.session.add_all([account, email])
        db.session.flush()
        db.session.add(
            Opportunity(
                source_key="gmail:assessment-today",
                email_message_id=email.id,
                kind="job",
                title="Backend Intern",
                organization="NeuralStack",
                status="OA Received",
                source="Gmail",
                deadline=datetime.combine(date.today() + timedelta(days=1), time(17)),
            )
        )
        db.session.add(
            LifeItem(
                source_key="project:flightiq",
                title="FlightIQ",
                category="project",
                status="open",
                progress=20,
                deadline=datetime.combine(date.today() + timedelta(days=2), time(18)),
                working_directory=self.temp_dir.name,
                next_action="Finish dashboard and submission video.",
            )
        )
        db.session.commit()

        board = planning_board()
        week = board["plan_blocks"]["week"]

        application = next(block for block in week if block["event_type"] == "application")
        project = next(block for block in week if block["event_type"] == "repo")
        self.assertIn("hiring step", application["reason"])
        self.assertIn("gmail", application["source_signals"])
        self.assertEqual(project["progress"], 20)
        self.assertIn("local_workspace", project["source_signals"])
        self.assertTrue(board["briefing"]["at_risk"])


if __name__ == "__main__":
    unittest.main()
