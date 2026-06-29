import os
import tempfile
import unittest
from pathlib import Path

from app.services import startup


@unittest.skipUnless(os.name == "nt", "Windows startup launcher tests require the per-user Startup folder.")
class StartupServicesTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = str(Path(self.temp_dir.name) / "AppData" / "Roaming")

    def tearDown(self):
        if self.original_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self.original_appdata
        self.temp_dir.cleanup()

    def test_windows_startup_path_is_per_user(self):
        path = startup.startup_entry_path()
        self.assertEqual(path.name, "AiOS Assistant Startup.cmd")
        self.assertIn("Startup", str(path))
        self.assertTrue(str(path).startswith(os.environ["APPDATA"]))

    def test_launcher_starts_desktop_app_once(self):
        launcher = startup.build_windows_launcher()
        self.assertTrue("AiOS-Assistant.exe" in launcher or "desktop_app.py" in launcher)
        self.assertNotIn("--worker", launcher)

    def test_install_and_remove_startup_entry(self):
        result = startup.install_startup_entry()
        path = Path(result["path"])
        self.assertTrue(path.exists())
        self.assertNotIn("--worker", path.read_text(encoding="utf-8"))

        startup.remove_startup_entry()
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
