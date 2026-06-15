from dataclasses import dataclass
from datetime import datetime
import csv
import json
from pathlib import Path

from app.models import ConnectorRun, Reminder, db
from app.services.data_pipelines import SUPPORTED_IMPORTS, import_source_file
from app.services.hackathons import detect_platform, ingest_hackathon_signal
from app.services.notifications import send_desktop_notification
from app.services.placements import ingest_placement_signal, is_neopat_signal


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
    description = "Scans Gmail for hackathon, application, shortlist, deadline, submission, and result updates."

    def status(self, app_config):
        mbox_path = app_config.get("GMAIL_MBOX_PATH", "")
        credentials_path = app_config.get("GMAIL_CREDENTIALS_PATH", "")
        token_path = app_config.get("GMAIL_TOKEN_PATH", "")
        configured = bool(mbox_path and Path(mbox_path).exists()) or bool(token_path and Path(token_path).exists())

        setup = "Set GMAIL_MBOX_PATH to a Gmail Takeout .mbox file for local import."
        if credentials_path and Path(credentials_path).exists() and not (token_path and Path(token_path).exists()):
            setup = "Google credentials found. Run this connector once to approve read-only Gmail access."
        if configured:
            setup = "Ready."

        return {
            "id": self.connector_id,
            "name": self.name,
            "description": self.description,
            "configured": configured,
            "setup": setup,
        }

    def run(self, app_config, classifier, provider, model=None, interactive=False):
        token_path = app_config.get("GMAIL_TOKEN_PATH", "")
        credentials_path = app_config.get("GMAIL_CREDENTIALS_PATH", "")
        if (token_path and Path(token_path).exists()) or (
            credentials_path and Path(credentials_path).exists()
        ):
            return self._run_gmail_api(app_config, classifier, interactive=interactive)

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

    def _run_gmail_api(self, app_config, classifier, interactive=False):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError:
            return ConnectorResult(
                connector_id=self.connector_id,
                status="setup_required",
                message="Install Gmail dependencies with pip install -r requirements.txt.",
            )

        scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
        token_path = Path(app_config.get("GMAIL_TOKEN_PATH", "credentials/gmail_token.json"))
        credentials_path = Path(
            app_config.get("GMAIL_CREDENTIALS_PATH", "credentials/google_client_secret.json")
        )
        credentials = None

        if token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            if not interactive:
                return ConnectorResult(
                    connector_id=self.connector_id,
                    status="setup_required",
                    message="Google is not connected. Use Connect Google, then run the Gmail scan.",
                )
            if not credentials_path.exists():
                return ConnectorResult(
                    connector_id=self.connector_id,
                    status="setup_required",
                    message=f"Missing Gmail OAuth credentials: {credentials_path}",
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
            credentials = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(credentials.to_json(), encoding="utf-8")

        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        query = app_config.get("GMAIL_OPPORTUNITY_QUERY") or app_config.get("GMAIL_HACKATHON_QUERY") or (
            "newer_than:365d (from:unstop.com OR from:hack2skill.com OR "
            "from:hackerearth.com OR from:devfolio.co OR from:devpost.com OR "
            "subject:hackathon OR subject:submission OR subject:shortlisted OR "
            "subject:application OR subject:applied OR subject:interview OR "
            "subject:assessment OR subject:\"online assessment\" OR subject:offer OR "
            "subject:rejected OR subject:rejection OR subject:intern OR subject:placement OR "
            "subject:neopat)"
        )
        try:
            response = service.users().messages().list(userId="me", q=query, maxResults=100).execute()
        except HttpError as exc:
            return ConnectorResult(
                connector_id=self.connector_id,
                status="setup_required",
                message=f"Gmail API request failed. {format_google_api_error(exc)}",
            )
        messages = response.get("messages", [])
        imported = 0
        hackathon_imported = 0
        placement_imported = 0
        neopat_imported = 0

        for item in messages:
            try:
                message = service.users().messages().get(
                    userId="me",
                    id=item["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
            except HttpError:
                continue
            headers = {
                header["name"].lower(): header["value"]
                for header in message.get("payload", {}).get("headers", [])
            }
            subject = headers.get("subject") or "Gmail update"
            sender = headers.get("from", "")
            snippet = message.get("snippet", "")
            occurred_at = datetime.fromtimestamp(int(message.get("internalDate", "0")) / 1000)
            classification = classifier.classify(subject, snippet)
            platform = detect_platform(sender, subject, snippet)

            if classification.category == "hackathon" or platform != "other":
                _opportunity, _update, created = ingest_hackathon_signal(
                    title=subject,
                    source=f"gmail:{sender}",
                    body=snippet,
                    organization=sender,
                    platform=platform,
                    status=classification.status,
                    deadline=classification.deadline,
                    external_id=f"gmail:hackathon:{item['id']}",
                    occurred_at=occurred_at,
                )
                hackathon_imported += int(created)
            elif classification.category in {"job", "interview", "deadline", "meeting"}:
                is_neopat = is_neopat_signal(subject, sender, snippet)
                _opportunity, _update, created = ingest_placement_signal(
                    title=classification.title or subject,
                    source=f"gmail:{sender}",
                    body=snippet,
                    organization=classification.organization or sender,
                    status=classification.status,
                    kind="neopat" if is_neopat else "job",
                    deadline=classification.deadline,
                    external_id=f"gmail:placement:{item['id']}",
                    occurred_at=occurred_at,
                )
                if is_neopat:
                    neopat_imported += int(created)
                else:
                    placement_imported += int(created)
            # Gmail requests are network-bound. Release SQLite's write lock after
            # each idempotent message so WDYD and the live dashboard stay writable.
            db.session.commit()

        imported = hackathon_imported + placement_imported + neopat_imported

        return ConnectorResult(
            connector_id=self.connector_id,
            status="ok",
            message=(
                f"Scanned {len(messages)} matching Gmail messages and imported "
                f"{hackathon_imported} hackathon updates, {placement_imported} placement updates, "
                f"and {neopat_imported} NeoPat updates."
            ),
            records_seen=len(messages),
            records_imported=imported,
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
    token_path = Path(app_config.get("GMAIL_TOKEN_PATH", "credentials/gmail_token.json"))
    credentials_path = Path(app_config.get("GMAIL_CREDENTIALS_PATH", "credentials/google_client_secret.json"))
    result = {
        "credentials_ready": credentials_path.exists(),
        "connected": False,
        "account": None,
        "message": "Google OAuth client is not configured.",
    }
    if not credentials_path.exists():
        return result
    result["message"] = "Ready to connect Google."
    if not token_path.exists():
        return result

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
        credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        result["connected"] = bool(credentials.valid)
        result["message"] = "Google connected." if credentials.valid else "Google authorization expired."
        if credentials.valid and include_profile:
            from googleapiclient.discovery import build

            profile = (
                build("gmail", "v1", credentials=credentials, cache_discovery=False)
                .users()
                .getProfile(userId="me")
                .execute()
            )
            result["account"] = profile.get("emailAddress")
    except Exception as exc:
        result["message"] = f"Google connection needs attention: {exc}"
    return result


def connect_gmail(app_config):
    credentials_path = Path(app_config.get("GMAIL_CREDENTIALS_PATH", "credentials/google_client_secret.json"))
    token_path = Path(app_config.get("GMAIL_TOKEN_PATH", "credentials/gmail_token.json"))
    if not credentials_path.exists():
        return {
            "connected": False,
            "message": "This build has no Google Desktop OAuth client configured.",
        }

    from google_auth_oauthlib.flow import InstalledAppFlow

    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    credentials = flow.run_local_server(port=0, open_browser=True, prompt="consent")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    try:
        __import__("os").chmod(token_path, 0o600)
    except OSError:
        pass
    return gmail_oauth_status(app_config, include_profile=True)


def disconnect_gmail(app_config):
    token_path = Path(app_config.get("GMAIL_TOKEN_PATH", "credentials/gmail_token.json"))
    token_path.unlink(missing_ok=True)
    return {"connected": False, "message": "Google disconnected. The local Gmail token was removed."}


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
