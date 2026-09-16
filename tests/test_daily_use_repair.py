import sqlite3
import tempfile
import unittest
from pathlib import Path


class DailyUseRepairTestCase(unittest.TestCase):
    def test_database_diagnostic_copies_before_inspection(self):
        from app.services.database_diagnostics import diagnose_sqlite_copy

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "source.db"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute("CREATE TABLE safe_data (id INTEGER PRIMARY KEY, value TEXT)")
                connection.execute("INSERT INTO safe_data(value) VALUES ('private')")
                connection.commit()
            finally:
                connection.close()

            report = diagnose_sqlite_copy(database_path, root / "diagnostics")

            self.assertTrue(report["ok"])
            self.assertEqual(report["source_path"], str(database_path.resolve()))
            self.assertTrue(Path(report["copy_path"]).exists())
            self.assertEqual(report["integrity"], "ok")


if __name__ == "__main__":
    unittest.main()
