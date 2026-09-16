import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


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

    def test_manual_application_status_survives_session_restart(self):
        from app import create_app
        from app.models import ApplicationRecord, db
        from app.services.application_lifecycle import record_application_decision

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "applications.db"

            class Config:
                TESTING = True
                SECRET_KEY = "test-secret"
                SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
                SQLALCHEMY_TRACK_MODIFICATIONS = False
                USER_DISPLAY_NAME = "Test User"

            app = create_app(Config)
            engine = None
            try:
                with app.app_context():
                    engine = db.engine
                    record = ApplicationRecord(
                        source_key="application:acme:backend-intern",
                        company="Acme",
                        normalized_company="acme",
                        role="Backend Intern",
                        normalized_role="backend intern",
                        status="to_apply",
                    )
                    db.session.add(record)
                    db.session.flush()
                    record_application_decision(record, "applied", "user", "Submitted on portal")
                    db.session.commit()
                    record_id = record.id

                    db.session.remove()
                    restored = db.session.get(ApplicationRecord, record_id)
                    self.assertEqual(restored.status, "applied")
                    self.assertEqual(restored.decisions[-1].reason, "Submitted on portal")
            finally:
                with app.app_context():
                    db.session.remove()
                if engine is not None:
                    engine.dispose()

    def test_same_company_different_roles_remain_separate_records(self):
        from app import create_app
        from app.models import ApplicationRecord, ConnectedAccount, EmailMessage, db
        from app.services.application_lifecycle import upsert_application_evidence

        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "roles.db"

            class Config:
                TESTING = True
                SECRET_KEY = "test-secret"
                SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path.as_posix()}"
                SQLALCHEMY_TRACK_MODIFICATIONS = False
                USER_DISPLAY_NAME = "Test User"

            app = create_app(Config)
            engine = None
            try:
                with app.app_context():
                    engine = db.engine
                    account = ConnectedAccount(provider="google", email="career@example.com")
                    db.session.add(account)
                    db.session.flush()
                    backend_email = EmailMessage(
                        account=account,
                        provider_message_id="backend-opening",
                        subject="Backend Intern at Acme",
                        sent_at=datetime(2026, 9, 16, 9, 0),
                    )
                    data_email = EmailMessage(
                        account=account,
                        provider_message_id="data-opening",
                        subject="Data Intern at Acme",
                        sent_at=datetime(2026, 9, 16, 10, 0),
                    )
                    db.session.add_all([backend_email, data_email])
                    db.session.flush()

                    backend = upsert_application_evidence(
                        backend_email,
                        {"company": "Acme", "role": "Backend Intern", "kind": "opening"},
                    )
                    data = upsert_application_evidence(
                        data_email,
                        {"company": "Acme", "role": "Data Intern", "kind": "opening"},
                    )
                    db.session.commit()

                    self.assertNotEqual(backend.id, data.id)
                    self.assertEqual(ApplicationRecord.query.count(), 2)
            finally:
                with app.app_context():
                    db.session.remove()
                if engine is not None:
                    engine.dispose()

    def test_incomplete_application_mail_is_retained_as_to_apply(self):
        from app.services.application_intelligence import classify_career_email

        email = SimpleNamespace(
            sender="Myntra Careers <careers@myntra.example>",
            subject="Complete your application to Myntra",
            snippet="Continue your software engineering intern application.",
            body_text="Please complete your application to Myntra before Friday.",
            labels_json="[]",
            insight=None,
            account=None,
            sent_at=datetime(2026, 9, 16, 9, 0),
            created_at=datetime(2026, 9, 16, 9, 0),
        )

        signal = classify_career_email(email)

        self.assertIsNotNone(signal)
        self.assertEqual(signal["kind"], "incomplete")
        self.assertEqual(signal["lifecycle_status"], "to_apply")


if __name__ == "__main__":
    unittest.main()
