import tempfile
import unittest
from pathlib import Path

from automation_agent import AutomationEngine
from automation_agent.config import AutomationConfig


class AutomationAgentTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "workspace"
        self.root.mkdir()
        self.config = AutomationConfig(
            data_dir=Path(self.temp_dir.name) / "data",
            allowed_roots=(self.root.resolve(),),
            max_batch_files=50,
        )
        self.engine = AutomationEngine(self.config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_organize_plan_requires_approval_and_moves_files(self):
        (self.root / "notes.pdf").write_text("report", encoding="utf-8")
        (self.root / "photo.png").write_bytes(b"not-a-real-image")
        plan = self.engine.create_plan(
            "Organize this folder",
            {"source": str(self.root)},
        )
        self.assertEqual(plan["status"], "planned")
        with self.assertRaises(PermissionError):
            self.engine.execute_plan(plan["id"], "wrong-token")

        result = self.engine.execute_plan(plan["id"], plan["approval_token"])
        self.assertEqual(result["status"], "completed")
        self.assertTrue((self.root / "Documents" / "notes.pdf").exists())
        self.assertTrue((self.root / "Images" / "photo.png").exists())

    def test_quarantine_can_be_restored(self):
        source = self.root / "temporary.txt"
        source.write_text("keep me", encoding="utf-8")
        plan = self.engine.create_plan(
            f'Delete "{source}"',
            {"source": str(source)},
        )
        result = self.engine.execute_plan(plan["id"], plan["approval_token"])
        self.assertFalse(source.exists())
        action = result["actions"][0]
        restored = self.engine.restore_action(action["id"])
        self.assertTrue(restored["ok"])
        self.assertTrue(source.exists())

    def test_outside_root_is_rejected(self):
        outside = Path(self.temp_dir.name) / "outside"
        outside.mkdir()
        with self.assertRaises(ValueError):
            self.engine.create_plan("Find duplicates", {"source": str(outside)})


if __name__ == "__main__":
    unittest.main()
