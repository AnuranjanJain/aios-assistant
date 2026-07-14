from dataclasses import dataclass
import csv
import json
from pathlib import Path

from app.models import ConnectorRun, Reminder, db
from app.services.data_pipelines import SUPPORTED_IMPORTS, import_source_file
from app.services.hackathons import ingest_hackathon_signal
from app.services.notifications import notification_center


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

    def run(self, app_config, classifier, provider, model=None, interactive=False):
        raise NotImplementedError


class GmailConnector(BaseConnector):
    connector_id = "gmail"
    name = "Gmail"
    description = "Synchronizes every connected Gmail account into local email intelligence."

    def status(self, app_config):
        from app.services.email_intelligence import google_client_status, list_accounts

        mbox_path = app_config.get("GMAIL_MBOX_PATH", "")
        accounts = list_accounts()
        client = google_client_status(app_config)
        configured = bool(accounts) or bool(mbox_path and Path(mbox_path).exists())
        if accounts:
            enabled = sum(1 for account in accounts if account["sync_enabled"])
            setup = f"{len(accounts)} accounts connected; {enabled} syncing in the background."
        elif client["ready"]:
            setup = "OAuth is ready. Connect your first Google account in Settings."
        else:
            setup = "Import a Google Desktop OAuth client in Settings, or configure a Gmail Takeout mbox."

        return {
            "id": self.connector_id,
            "name": self.name,
            "description": self.description,
            "configured": configured,
            "setup": setup,
        }

    def run(self, app_config, classifier, provider, model=None, interactive=False):
        from app.models import ConnectedAccount
        from app.services.email_intelligence import run_email_intelligence_cycle

        accounts = ConnectedAccount.query.filter_by(provider="google").count()
        if accounts:
            result = run_email_intelligence_cycle(app_config)
            sync_results = result.get("sync", [])
            seen = sum(int(item.get("seen", 0)) for item in sync_results)
            imported = sum(int(item.get("imported", 0)) for item in sync_results)
            failures = [item for item in sync_results if not item.get("ok")]
            return ConnectorResult(
                connector_id=self.connector_id,
                status="partial" if failures else "ok",
                message=(
                    f"Synced {len(sync_results)} Gmail accounts, checked {seen} changed messages, "
                    f"and stored {imported} new messages locally."
                    + (f" {len(failures)} accounts need attention." if failures else "")
                ),
                records_seen=seen,
                records_imported=imported,
            )

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
            message="No Gmail account is connected. Open Settings, import a Google Desktop OAuth client, then connect an account.",
        )


class ReminderConnector(BaseConnector):
    connector_id = "reminders"
    name = "Local Reminders"
    description = "Checks open reminders and triggers desktop notifications for due items."

    def run(self, app_config, classifier, provider, model=None):
        result = notification_center(send=True)
        generated = len(result["generated"])
        sent = result["dispatched"]["sent"]

        return ConnectorResult(
            connector_id=self.connector_id,
            status="ok",
            message=f"Generated {generated} smart notifications and sent {sent} desktop notifications.",
            records_seen=len(result["notifications"]),
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


class HackathonPlatformConnector(BaseConnector):
    connector_id = "hackathon_platforms"
    name = "Hackathon Platforms"
    description = "Imports local exports from Unstop, Hack2Skill, HackerEarth, Devfolio, and Devpost."

    def status(self, app_config):
        import_dir = Path(app_config.get("HACKATHON_IMPORT_DIR", "imports/hackathons"))
        import_dir.mkdir(parents=True, exist_ok=True)
        return {
            "id": self.connector_id,
            "name": self.name,
            "description": self.description,
            "configured": True,
            "setup": f"Drop platform .json or .csv exports into {import_dir}. Known pages are also captured by the browser extension.",
        }

    def run(self, app_config, classifier, provider, model=None):
        import_dir = Path(app_config.get("HACKATHON_IMPORT_DIR", "imports/hackathons"))
        import_dir.mkdir(parents=True, exist_ok=True)
        records_seen = 0
        records_imported = 0

        for path in sorted(import_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".json", ".csv"}:
                continue

            for index, item in enumerate(read_hackathon_export(path)):
                records_seen += 1
                _opportunity, _update, created = ingest_hackathon_signal(
                    title=item.get("title") or item.get("name") or "Imported hackathon",
                    source=f"platform export:{path.name}",
                    body=item.get("notes") or item.get("description") or item.get("status") or "",
                    organization=item.get("organizer") or item.get("organization") or "",
                    platform=item.get("platform") or "",
                    url=item.get("url") or item.get("link") or "",
                    status=item.get("status") or "",
                    deadline=item.get("deadline") or item.get("submission_deadline"),
                    external_id=str(item.get("id") or f"platform:{path.name}:{index}"),
                    occurred_at=item.get("updated_at") or item.get("date"),
                )
                records_imported += int(created)

        return ConnectorResult(
            connector_id=self.connector_id,
            status="ok",
            message=f"Scanned {records_seen} platform records and imported {records_imported} new updates.",
            records_seen=records_seen,
            records_imported=records_imported,
        )


def read_hackathon_export(path):
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload if isinstance(payload, list) else payload.get("hackathons", payload.get("items", []))
        return [item for item in items if isinstance(item, dict)]

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def format_google_api_error(exc):
    try:
        payload = json.loads(exc.content.decode("utf-8"))
        details = payload.get("error", {})
        message = details.get("message", "")
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        message = str(exc)

    if "Gmail API has not been used" in message or "disabled" in message:
        return "Enable Gmail API for the Google Cloud project attached to credentials/google_client_secret.json, wait a minute, then run Gmail again."
    return message or "Check Google Cloud API settings and OAuth consent configuration."


CONNECTORS = {
    "gmail": GmailConnector(),
    "reminders": ReminderConnector(),
    "job_portals": JobPortalConnector(),
    "hackathon_platforms": HackathonPlatformConnector(),
}


def gmail_oauth_status(app_config, include_profile=False):
    from app.services.email_intelligence import google_client_status, list_accounts

    client = google_client_status(app_config)
    accounts = list_accounts()
    result = {
        "credentials_ready": client["ready"],
        "connected": bool(accounts),
        "account": accounts[0]["email"] if len(accounts) == 1 else None,
        "accounts": accounts,
        "account_count": len(accounts),
        "message": (
            f"{len(accounts)} Google accounts connected."
            if accounts
            else client["message"]
        ),
    }
    return result


def connect_gmail(app_config):
    from app.services.email_intelligence import connect_google_account

    result = connect_google_account(app_config)
    return {
        "connected": bool(result.get("ok")),
        "account": (result.get("account") or {}).get("email"),
        "message": result.get("message", "Google connection finished."),
    }


def disconnect_gmail(app_config):
    return {
        "connected": False,
        "message": "Manage individual Google accounts in Settings so one account is never removed by accident.",
    }


def list_connectors(app_config):
    return [connector.status(app_config) for connector in CONNECTORS.values()]


def run_connector(
    connector_id,
    app_config,
    classifier,
    provider,
    model=None,
    interactive=False,
    record_run=True,
):
    connector = CONNECTORS.get(connector_id)
    if not connector:
        return ConnectorResult(connector_id, "not_found", f"Unknown connector: {connector_id}")

    if connector_id == "gmail":
        result = connector.run(
            app_config,
            classifier,
            provider,
            model=model,
            interactive=interactive,
        )
    else:
        result = connector.run(app_config, classifier, provider, model=model)
    if record_run or result.status != "ok":
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
