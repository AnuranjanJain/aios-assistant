import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_paths import configure_desktop_environment


class RuntimePathsTestCase(unittest.TestCase):
    def test_desktop_always_uses_database_in_persistent_data_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "AiOS data"
            environment = {
                "AIOS_DATA_DIR": str(data_dir),
                "DATABASE_URL": "sqlite:///stale-launch-specific.db",
                "AIOS_INSTANCE_PATH": str(Path(temp_dir) / "stale-instance"),
            }
            with patch.dict(os.environ, environment, clear=False):
                paths = configure_desktop_environment()

                self.assertEqual(paths.data_dir, data_dir.resolve())
                self.assertEqual(
                    os.environ["DATABASE_URL"],
                    f"sqlite:///{(data_dir.resolve() / 'aios_assistant.db').as_posix()}",
                )
                self.assertEqual(os.environ["AIOS_INSTANCE_PATH"], str(data_dir.resolve() / "instance"))


if __name__ == "__main__":
    unittest.main()
