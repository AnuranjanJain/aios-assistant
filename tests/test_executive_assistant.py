import json
import tempfile
import unittest
from datetime import date, datetime, time, timedelta
from pathlib import Path

from app import create_app
from app.models import (
    ConnectedAccount,
    EmailInsight,
    EmailMessage,
    EmailThread,
    GitHubRepository,
    LearningItem,
    LifeItem,
    MemoryEntity,
    Opportunity,
    PlanningEvent,
    db,
)
from app.services.executive_assistant import answer_executive_question, executive_briefing


class ExecutiveAssistantTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "executive-assistant-test.db"

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

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def seed_life_os_graph(self):
        today = date.today()
        account = ConnectedAccount(provider="google", email="assistant@example.com")
        thread = EmailThread(account=account, provider_thread_id="thread-flightiq", subject="FlightIQ sponsor reply")
        email = EmailMessage(
            account=account,
            thread=thread,
            provider_message_id="msg-flightiq",
            provider_thread_id="thread-flightiq",
            sender="riya@amazon.example",
            subject="FlightIQ sponsor reply needed",
            body_text="Can you reply with the hackathon plan before Friday?",
            is_unread=True,
            sent_at=datetime.combine(today - timedelta(days=4), time(10)),
        )
        flightiq = LifeItem(
            source_key="life:flightiq",
            title="FlightIQ Hackathon",
            category="hackathon",
            priority="high",
            status="open",
            deadline=datetime.combine(today + timedelta(days=2), time(18)),
            progress=0.45,
            next_action="Finish prototype and reply to sponsor.",
        )
        internship = LifeItem(
            source_key="life:amazon-internship",
            title="Amazon internship application",
            category="internship",
            priority="urgent",
            status="open",
            deadline=datetime.combine(today + timedelta(days=1), time(17)),
            next_action="Submit final resume and eligibility form.",
        )
        db.session.add_all([account, thread, email, flightiq, internship])
        db.session.flush()
        db.session.add(
            EmailInsight(
                email=email,
                life_item=flightiq,
                priority="high",
                urgency="high",
                category="hackathon",
                summary="Sponsor needs a reply about the FlightIQ plan.",
                action_items_json=json.dumps(["Reply to sponsor", "Send updated plan"]),
                deadlines_json=json.dumps(["before Friday"]),
                meetings_json=json.dumps(["FlightIQ review call"]),
                follow_ups_json=json.dumps(["Reply to Riya"]),
                waiting_on_json=json.dumps([]),
                projects_json=json.dumps(["FlightIQ"]),
                people_json=json.dumps(["Riya"]),
                companies_json=json.dumps(["Amazon"]),
                suggested_actions_json=json.dumps(["Reply with hackathon plan"]),
                confidence=0.9,
            )
        )
        db.session.add_all(
            [
                Opportunity(
                    kind="hackathon",
                    title="FlightIQ Challenge",
                    organization="Amazon",
                    status="Applied",
                    deadline=datetime.combine(today + timedelta(days=2), time(18)),
                    notes="Prototype, sponsor reply, and demo video remain.",
                ),
                GitHubRepository(
                    repo_full_name="AnuranjanJain/flightiq",
                    html_url="https://github.com/AnuranjanJain/flightiq",
                    life_item=flightiq,
                    inactive=True,
                    completion_percentage=55,
                    current_sprint="Demo polish",
                    remaining_work="Dashboard, pitch video, and test data.",
                    suggested_next_task="Ship the dashboard summary card.",
                    commits_json=json.dumps(
                        [
                            {
                                "sha": "abc123",
                                "message": "add flight dashboard",
                                "date": datetime.combine(today - timedelta(days=3), time(12)).isoformat(),
                            }
                        ]
                    ),
                ),
                LearningItem(
                    life_item=flightiq,
                    item_type="video",
                    title="GenAI attention mechanism video",
                    project="FlightIQ",
                    status="in_progress",
                    completion=0.3,
                    estimated_minutes=45,
                    next_revision_at=datetime.combine(today, time(19)),
                    projects_json=json.dumps(["FlightIQ"]),
                ),
                PlanningEvent(
                    source_key="exec:meeting",
                    event_type="meeting",
                    source="calendar",
                    title="FlightIQ review meeting",
                    project="FlightIQ",
                    planned_start=datetime.combine(today, time(16)),
                    planned_minutes=30,
                    priority="high",
                    status="planned",
                    work_left="Prepare sponsor update.",
                ),
                PlanningEvent(
                    source_key="exec:blocker",
                    event_type="repo",
                    source="github",
                    title="FlightIQ demo blocker",
                    project="FlightIQ",
                    deadline=datetime.combine(today + timedelta(days=1), time(17)),
                    planned_minutes=120,
                    priority="urgent",
                    status="blocked",
                    work_left="Need sample route data.",
                    repo_url="https://github.com/AnuranjanJain/flightiq",
                ),
                MemoryEntity(
                    entity_type="project",
                    name="FlightIQ",
                    slug="flightiq",
                    status="active",
                    summary="Hackathon project connected to repo, email, meeting, and GenAI learning.",
                ),
            ]
        )
        db.session.commit()

    def test_executive_assistant_answers_required_questions_from_complete_graph(self):
        questions = [
            "What should I do now?",
            "What am I forgetting?",
            "What projects are at risk?",
            "Which internship deadline is closest?",
            "What emails need replies?",
            "How much work is left?",
            "Can I finish before Friday?",
            "Which GenAI video should I watch next?",
            "What hackathon deserves today's focus?",
        ]
        with self.app.app_context():
            self.seed_life_os_graph()
            answers = [answer_executive_question(question, {"AI_PROVIDER": "rule_based"}) for question in questions]

        self.assertEqual(len(answers), len(questions))
        for answer in answers:
            self.assertTrue(answer["ok"])
            self.assertTrue(answer["graph_used"])
            self.assertGreater(answer["graph_scope"]["nodes"], 8)
            self.assertIn("emails", answer["evidence_domains"])
            self.assertIn("hackathons", answer["evidence_domains"])
            self.assertIn("learning", answer["evidence_domains"])
            self.assertIn("analytics", answer["evidence_domains"])

        by_intent = {answer["intent"]: answer for answer in answers}
        self.assertIn("FlightIQ", by_intent["now"]["answer"])
        self.assertIn("FlightIQ", by_intent["risk"]["answer"])
        self.assertIn("Amazon internship", by_intent["internship_deadline"]["answer"])
        self.assertIn("sponsor reply", by_intent["email_replies"]["answer"].lower())
        self.assertGreater(by_intent["work_left"]["planned_hours"], 0)
        self.assertIn("target_date", by_intent["finish_before"])
        self.assertIn("GenAI attention", by_intent["genai_video"]["answer"])
        self.assertIn("FlightIQ Challenge", by_intent["hackathon_focus"]["answer"])

    def test_executive_assistant_api_supports_briefing_and_single_question(self):
        with self.app.app_context():
            self.seed_life_os_graph()

        briefing = self.client.get("/api/executive-assistant", headers={"X-AiOS-Token": "local-test-token"})
        single = self.client.post(
            "/api/executive-assistant",
            headers={"X-AiOS-Token": "local-test-token"},
            json={"question": "What emails need replies?"},
        )

        self.assertEqual(briefing.status_code, 200)
        self.assertEqual(len(briefing.get_json()["assistant"]), 9)
        self.assertEqual(single.status_code, 200)
        self.assertEqual(single.get_json()["intent"], "email_replies")
        self.assertTrue(single.get_json()["graph_used"])


if __name__ == "__main__":
    unittest.main()
