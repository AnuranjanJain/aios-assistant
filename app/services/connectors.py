from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.models import ConnectorRun, Reminder, db
from app.services.data_pipelines import SUPPORTED_IMPORTS, import_source_file
from app.services.notifications import send_desktop_notification


@dataclass
class ConnectorResult:
    connector_id: str
    status: str
    message: str
    records_seen: int = 0
    records_imported: int = 0


class BaseConnector:
    connector_id = "base"
    name = "Base Connector"
    description = ""

    def status(self, app_config):
        return {
            "id": self.connector_id,
            "name": self.name,
            "description": self.description,
            "configured": True,
            "setup": "",
        }

    def run(self, app_config, classifier, provider, model=None):
        raise NotImplementedError


class GmailConnector(BaseConnector):
    connector_id = "gmail"
    name = "Gmail"
    description = "Imports real Gmail data from Takeout mbox now; OAuth API support is prepared for credentials."

    def status(self, app_config):
        mbox_path = app_config.get("GMAIL_MBOX_PATH", "")
        credentials_path = app_config.get("GMAIL_CREDENTIALS_PATH", "")
        token_path = app_config.get("GMAIL_TOKEN_PATH", "")
        configured = bool(mbox_path and Path(mbox_path).exists()) or bool(Path(token_path).exists())

        setup = "Set GMAIL_MBOX_PATH to a Gmail Takeout .mbox file for local import."
        if Path(credentials_path).exists() and not Path(token_path).exists():
            setup = "Google credentials found. OAuth token flow still needs to be completed."
        if configured:
            setup = "Ready."

        return {
            "id": self.connector_id,
            "name": self.name,
            "description": self.description,
            "configured": configured,
            "setup": setup,
        }

    def run(self, app_config, classifier, provider, model=None):
        mbox_path = app_config.get("GMAIL_MBOX_PATH", "")
        if mbox_path and Path(mbox_path).exists():
            imported = import_source_file(mbox_path, classifier, provider, model=model, limit=100)
            return ConnectorResult(
                connector_id=self.connector_id,
                status="ok",
                message=f"Imported {len(imported)} Gmail records from Takeout mbox.",
                records_seen=len(imported),
                records_imported=len(imported),
            )

        return ConnectorResult(
            connector_id=self.connector_id,
            status="setup_required",
            message="No Gmail source configured. Add GMAIL_MBOX_PATH for local import or configure Gmail OAuth credentials.",
        )


class ReminderConnector(BaseConnector):
    connector_id = "reminders"
    name = "Local Reminders"
    description = "Checks open reminders and triggers desktop notifications for due items."

    def run(self, app_config, classifier, provider, model=None):
        due_reminders = (
            Reminder.query.filter(Reminder.is_done.is_(False))
            .filter(Reminder.is_read.is_(False))
            .order_by(Reminder.due_at.asc())
            .limit(10)
            .all()
        )
        sent = 0
        for reminder in due_reminders:
            if send_desktop_notification("AiOS Reminder", reminder.title):
                sent += 1
                reminder.is_read = True
                reminder.notified_at = datetime.utcnow()

        return ConnectorResult(
            connector_id=self.connector_id,
            status="ok",
            message=f"Checked {len(due_reminders)} reminders and sent {sent} desktop notifications.",
            records_seen=len(due_reminders),
            records_imported=sent,
        )


class JobPortalConnector(BaseConnector):
    connector_id = "job_portals"
    name = "Job Portals"
    description = "Imports saved job portal exports and works with the browser extension for live page capture."

    def status(self, app_config):
        import_dir = Path(app_config.get("JOB_PORTAL_IMPORT_DIR", "imports/job_portals"))
        configured = import_dir.exists()
        return {
            "id": self.connector_id,
            "name": self.name,
            "description": self.description,
            "configured": configured,
            "setup": f"Drop .json or .csv job exports into {import_dir}. Browser extension capture is always available.",
        }

    def run(self, app_config, classifier, provider, model=None):
        import_dir = Path(app_config.get("JOB_PORTAL_IMPORT_DIR", "imports/job_portals"))
        import_dir.mkdir(parents=True, exist_ok=True)

        records_seen = 0
        records_imported = 0
        for path in sorted(import_dir.iterdir()):
            if path.suffix.lower() not in SUPPORTED_IMPORTS:
                continue
            imported = import_source_file(path, classifier, provider, model=model, limit=100)
            records_seen += len(imported)
            records_imported += len(imported)

        return ConnectorResult(
            connector_id=self.connector_id,
            status="ok",
            message=f"Imported {records_imported} job portal records from {import_dir}.",
            records_seen=records_seen,
            records_imported=records_imported,
        )


CONNECTORS = {
    "gmail": GmailConnector(),
    "reminders": ReminderConnector(),
    "job_portals": JobPortalConnector(),
}


def list_connectors(app_config):
    return [connector.status(app_config) for connector in CONNECTORS.values()]


def run_connector(connector_id, app_config, classifier, provider, model=None):
    connector = CONNECTORS.get(connector_id)
    if not connector:
        return ConnectorResult(connector_id, "not_found", f"Unknown connector: {connector_id}")

    result = connector.run(app_config, classifier, provider, model=model)
    db.session.add(
        ConnectorRun(
            connector_id=result.connector_id,
            status=result.status,
            message=result.message,
            records_seen=result.records_seen,
            records_imported=result.records_imported,
        )
    )
    return result
