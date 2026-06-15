import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.models import MemoryEntity, WorkCheckpoint


class MemoryEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "memory-test.db"

        class TestConfig:
            TESTING = True
            SECRET_KEY = "test-secret"
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            LOCAL_API_TOKEN = ""
            OLLAMA_URL = "http://127.0.0.1:9"
            OLLAMA_MODEL = "qwen2.5:7b"
            OLLAMA_EMBED_MODEL = "nomic-embed-text"
            MEMORY_VECTOR_BACKEND = "sqlite"
            MEMORY_VECTOR_PATH = str(Path(self.temp_dir.name) / "vectors")
            USER_DISPLAY_NAME = "Anuranjan"

        self.config = TestConfig
        self.app = create_app(TestConfig)
        self.apps = [self.app]
        self.client = self.app.test_client()
        self.embedding_patch = patch("app.services.memory_engine.embed_text", return_value=[])
        self.embedding_patch.start()

    def tearDown(self):
        self.embedding_patch.stop()
        for app in self.apps:
            with app.app_context():
                from app.models import db

                db.session.remove()
                db.engine.dispose()
        self.temp_dir.cleanup()

    def test_project_checkpoint_and_natural_language_queries(self):
        response = self.client.post(
            "/api/memory/checkpoints",
            json={
                "project_name": "AiOS Project",
                "summary": "Built persistent memory schema",
                "open_files": ["memory_engine.py", "routes.py"],
                "active_tasks": ["Implement memory layer"],
                "next_actions": ["Add Ollama integration", "Test reboot persistence"],
            },
        )
        self.assertEqual(response.status_code, 201)

        unfinished = self.client.post(
            "/api/memory/ask",
            json={"query": "Show unfinished projects."},
        ).get_json()
        next_step = self.client.post(
            "/api/memory/ask",
            json={"query": "What was the next step for AiOS Project?"},
        ).get_json()

        self.assertIn("AiOS Project", unfinished["answer"])
        self.assertIn("Add Ollama integration", next_step["answer"])

    def test_user_root_and_automatic_knowledge_graph_relation(self):
        response = self.client.post(
            "/api/memory/entities",
            json={"entity_type": "skill", "name": "Python", "status": "active"},
        )
        self.assertEqual(response.status_code, 201)

        graph = self.client.get("/api/memory/graph").get_json()
        names = {node["name"] for node in graph["nodes"]}
        relation_types = {edge["relation_type"] for edge in graph["edges"]}

        self.assertIn("Anuranjan", names)
        self.assertIn("Python", names)
        self.assertIn("has_skill", relation_types)

    def test_memory_survives_application_restart(self):
        response = self.client.post(
            "/api/memory/checkpoints",
            json={
                "project_name": "Persistent Project",
                "summary": "Save this across application instances",
                "next_actions": ["Resume after reboot"],
            },
        )
        self.assertEqual(response.status_code, 201)

        restarted_app = create_app(self.config)
        self.apps.append(restarted_app)
        with restarted_app.app_context():
            project = MemoryEntity.query.filter_by(name="Persistent Project").one()
            checkpoint = WorkCheckpoint.query.filter_by(project_id=project.id).one()
            self.assertEqual(project.status, "active")
            self.assertIn("Resume after reboot", checkpoint.next_actions_json)


if __name__ == "__main__":
    unittest.main()
