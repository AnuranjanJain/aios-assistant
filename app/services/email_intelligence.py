import base64
import hashlib
import html
import json
import logging
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import wsgiref.simple_server
import wsgiref.util
from datetime import date, datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from time import monotonic

from flask import current_app

from runtime_paths import get_runtime_paths

from app.models import (
    AISuggestion,
    ConnectedAccount,
    DailyPlan,
    EmailAttachment,
    EmailInsight,
    EmailMessage,
    EmailTask,
    EmailThread,
    LifeItem,
    LifeItemRelation,
    OAuthToken,
    WeeklyPlan,
    db,
)


LOGGER = logging.getLogger(__name__)


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]

EMAIL_CATEGORIES = {
    "internship",
    "hackathon",
    "meeting",
    "assignment",
    "reminder",
    "finance",
    "travel",
    "shopping",
    "learning",
    "personal",
    "general",
}

IMPORTANT_CATEGORIES = {
    "internship",
    "hackathon",
    "meeting",
    "assignment",
    "reminder",
    "learning",
}


def _json(value, fallback=None):
    if fallback is None:
        fallback = []
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _dump(value):
    return json.dumps(value or [], ensure_ascii=False)


def _dump_object(value):
    return json.dumps(value or {}, ensure_ascii=False)


def _encryption_key():
    secret = current_app.config.get("SECRET_KEY", "local-dev-secret")
    digest = hashlib.sha256(f"{secret}:aios-email-oauth".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_token_json(token_json):
    from cryptography.fernet import Fernet

    return Fernet(_encryption_key()).encrypt(token_json.encode("utf-8")).decode("utf-8")


def decrypt_token_json(token_json_encrypted):
    from cryptography.fernet import Fernet

    return Fernet(_encryption_key()).decrypt(token_json_encrypted.encode("utf-8")).decode("utf-8")


def list_accounts():
    accounts = ConnectedAccount.query.order_by(ConnectedAccount.created_at.desc()).all()
    return [serialize_account(account) for account in accounts]


def serialize_account(account):
    return {
        "id": account.id,
        "provider": account.provider,
        "email": account.email,
        "display_name": account.display_name or "",
        "label": account.label or account.email,
        "sync_enabled": account.sync_enabled,
        "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
        "last_error": account.last_error or "",
        "status": "attention" if account.last_error else "paused" if not account.sync_enabled else "connected",
        "token_expires_at": account.oauth_token.expires_at.isoformat() if account.oauth_token and account.oauth_token.expires_at else None,
    }


def _google_credentials_path(app_config):
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        bundled = Path(bundle_root) / "app_credentials" / "google_client_secret.json"
        if bundled.exists():
            return bundled.resolve()

    configured = Path(app_config.get("GMAIL_CREDENTIALS_PATH") or "credentials/google_client_secret.json").expanduser()
    if configured.exists() or configured.is_absolute():
        return configured.resolve()
    return (get_runtime_paths().credentials_dir / "google_client_secret.json").resolve()


def google_client_status(app_config):
    path = _google_credentials_path(app_config)
    result = {
        "ready": False,
        "client_id_hint": "",
        "message": "Google sign-in is unavailable in this build.",
    }
    if not path.exists():
        return result
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        installed = payload.get("installed") if isinstance(payload, dict) else None
        if not isinstance(installed, dict):
            result["message"] = "This is not a Google Desktop app OAuth client file."
            return result
        required = ("client_id", "auth_uri", "token_uri")
        missing = [key for key in required if not str(installed.get(key) or "").strip()]
        if missing:
            result["message"] = f"OAuth client file is missing: {', '.join(missing)}."
            return result
        client_id = installed["client_id"]
        result.update(
            ready=True,
            client_id_hint=f"...{client_id[-18:]}",
            message="Google sign-in is ready.",
        )
    except (OSError, json.JSONDecodeError) as exc:
        result["message"] = f"OAuth client file could not be read: {exc}"
    return result


class _GoogleOAuthRedirectApp:
    def __init__(self):
        self.last_request_uri = ""

    def __call__(self, environ, start_response):
        self.last_request_uri = wsgiref.util.request_uri(environ)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.last_request_uri).query)
        error = (query.get("error") or [""])[0]
        succeeded = bool((query.get("code") or [""])[0]) and not error
        title = "Google account connected" if succeeded else "Google sign-in did not finish"
        message = (
            "You can close this browser tab and return to AiOS."
            if succeeded
            else "Return to AiOS for the next step. No email access was stored."
        )
        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#090b09;color:#f4f7f2;font:16px/1.55 system-ui,sans-serif}}
main{{width:min(520px,calc(100% - 40px));border:1px solid #293029;border-radius:16px;background:#121512;padding:32px;box-sizing:border-box}}
span{{display:grid;width:48px;height:48px;place-items:center;border-radius:12px;background:#a7ff3c;color:#10150c;font-weight:800}}
h1{{margin:22px 0 10px;font-size:28px;line-height:1.25}}p{{margin:0;color:#a7b0a4}}
</style></head><body><main><span>G</span><h1>{html.escape(title)}</h1><p>{html.escape(message)}</p></main></body></html>"""
        payload = body.encode("utf-8")
        start_response(
            "200 OK",
            [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload)))],
        )
        return [payload]


def _google_oauth_error_message(error):
    if error == "access_denied":
        return (
            "Google cancelled or blocked this request. If Google showed Access blocked, this account is not approved "
            "for the OAuth app yet. Add it as a test user, or publish and verify the OAuth app for universal access."
        )
    return "Google did not authorize Gmail access. No email access was stored."


def connect_google_account(
    app_config,
    label="",
    on_authorization=None,
    should_cancel=None,
    timeout_seconds=180,
    open_browser=True,
):
    credentials_path = _google_credentials_path(app_config)
    if not credentials_path.exists():
        return {"ok": False, "message": f"Missing Google OAuth client at {credentials_path}"}

    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    client_config = json.loads(credentials_path.read_text(encoding="utf-8"))
    client_config["installed"]["auth_uri"] = "https://accounts.google.com/o/oauth2/v2/auth"
    flow = InstalledAppFlow.from_client_config(
        client_config,
        GMAIL_SCOPES,
        autogenerate_code_verifier=True,
    )
    callback_app = _GoogleOAuthRedirectApp()
    wsgiref.simple_server.WSGIServer.allow_reuse_address = False
    callback_server = wsgiref.simple_server.make_server(
        "127.0.0.1",
        0,
        callback_app,
        handler_class=wsgiref.simple_server.WSGIRequestHandler,
    )
    try:
        flow.redirect_uri = f"http://127.0.0.1:{callback_server.server_port}/"
        authorization_url, _ = flow.authorization_url(
            prompt="select_account consent",
            access_type="offline",
            include_granted_scopes="true",
        )
        if callable(on_authorization):
            on_authorization(authorization_url)
        if open_browser:
            webbrowser.open(authorization_url, new=1, autoraise=True)

        deadline = monotonic() + max(30, int(timeout_seconds))
        while not callback_app.last_request_uri:
            if callable(should_cancel) and should_cancel():
                return {"ok": False, "status": "cancelled", "message": "Google sign-in was cancelled."}
            remaining = deadline - monotonic()
            if remaining <= 0:
                return {
                    "ok": False,
                    "status": "timed_out",
                    "message": (
                        "Google did not return to AiOS. If Google showed Access blocked, approve this account as a test user "
                        "or publish and verify the OAuth app, then retry."
                    ),
                }
            callback_server.timeout = min(0.5, remaining)
            callback_server.handle_request()

        query = urllib.parse.parse_qs(urllib.parse.urlsplit(callback_app.last_request_uri).query)
        oauth_error = (query.get("error") or [""])[0]
        if oauth_error:
            return {"ok": False, "status": "failed", "message": _google_oauth_error_message(oauth_error)}
        if not (query.get("code") or [""])[0]:
            return {"ok": False, "status": "failed", "message": "Google returned an incomplete sign-in response."}
        authorization_response = callback_app.last_request_uri.replace("http://", "https://", 1)
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
    finally:
        callback_server.server_close()

    if callable(should_cancel) and should_cancel():
        return {"ok": False, "status": "cancelled", "message": "Google sign-in was cancelled."}
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress", "").strip()
    if not email:
        return {"ok": False, "message": "Google did not return a Gmail profile email."}

    account = ConnectedAccount.query.filter_by(provider="google", email=email).first()
    if account is None:
        account = ConnectedAccount(provider="google", email=email, label=label or email)
        db.session.add(account)
        db.session.flush()
    account.display_name = account.display_name or email.split("@")[0]
    account.label = label or account.label or email
    account.sync_enabled = True
    account.last_error = None

    token = account.oauth_token or OAuthToken(account=account)
    token.token_json_encrypted = encrypt_token_json(credentials.to_json())
    token.scopes_json = _dump(GMAIL_SCOPES)
    token.expires_at = credentials.expiry
    db.session.add(token)
    db.session.commit()
    return {"ok": True, "account": serialize_account(account), "message": f"Connected {email}"}


def update_account(account_id, label=None, sync_enabled=None):
    account = db.session.get(ConnectedAccount, account_id)
    if account is None:
        return {"ok": False, "message": "Account not found."}
    if label is not None:
        account.label = str(label).strip()[:120] or account.email
    if sync_enabled is not None:
        account.sync_enabled = bool(sync_enabled)
    db.session.commit()
    return {"ok": True, "account": serialize_account(account)}


def remove_account(account_id, revoke=True):
    account = db.session.get(ConnectedAccount, account_id)
    if account is None:
        return {"ok": False, "message": "Account not found."}
    revoked = False
    if revoke and account.oauth_token:
        try:
            token_data = json.loads(decrypt_token_json(account.oauth_token.token_json_encrypted))
            revoke_token = token_data.get("refresh_token") or token_data.get("token")
            if revoke_token:
                body = urllib.parse.urlencode({"token": revoke_token}).encode("ascii")
                revoke_request = urllib.request.Request(
                    "https://oauth2.googleapis.com/revoke",
                    data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    method="POST",
                )
                with urllib.request.urlopen(revoke_request, timeout=5) as response:
                    revoked = response.status == 200
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError):
            revoked = False
    email = account.email
    db.session.delete(account)
    db.session.commit()
    return {
        "ok": True,
        "revoked": revoked,
        "message": f"Removed {email}." + (" Google access was revoked." if revoked else " The local token was deleted."),
    }


def credentials_for_account(account):
    if not account.oauth_token:
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    credentials = Credentials.from_authorized_user_info(
        json.loads(decrypt_token_json(account.oauth_token.token_json_encrypted)),
        GMAIL_SCOPES,
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        account.oauth_token.token_json_encrypted = encrypt_token_json(credentials.to_json())
        account.oauth_token.expires_at = credentials.expiry
    return credentials


def sync_all_accounts(limit_per_account=50):
    results = []
    for account in ConnectedAccount.query.filter_by(provider="google", sync_enabled=True).all():
        results.append(sync_account(account, limit=limit_per_account))
    db.session.commit()
    return results


def _friendly_sync_error(exc):
    raw_message = str(exc)
    lowered = raw_message.lower()
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status == 401 or "invalid_grant" in lowered or "expired or revoked" in lowered:
        return {
            "error_code": "google_access_expired",
            "message": "Google access expired. Your account and existing mail are still saved in AiOS.",
            "suggested_fix": "Remove this Google account, connect it again, then press Sync.",
        }
    if status == 403 or "insufficient permission" in lowered or "access_denied" in lowered:
        return {
            "error_code": "gmail_permission_denied",
            "message": "Google did not allow read-only Gmail access. Nothing was removed from AiOS.",
            "suggested_fix": "Confirm Gmail API is enabled and this address is an OAuth test user, then reconnect the account.",
        }
    if status == 429 or "rate limit" in lowered or "quota" in lowered:
        return {
            "error_code": "gmail_rate_limited",
            "message": "Gmail asked AiOS to slow down. Your account and synced mail remain saved.",
            "suggested_fix": "Wait a few minutes and press Sync once more.",
        }
    if isinstance(exc, (OSError, urllib.error.URLError)) or "timed out" in lowered:
        return {
            "error_code": "gmail_network_unavailable",
            "message": "AiOS could not reach Gmail. Your local email data is unchanged.",
            "suggested_fix": "Check your internet connection and retry Sync.",
        }
    return {
        "error_code": "gmail_sync_failed",
        "message": "Gmail sync could not finish. Your account and existing mail remain saved.",
        "suggested_fix": "Retry once. If it repeats, reconnect this Google account and sync again.",
    }


def sync_account(account, limit=50):
    if isinstance(account, int):
        account = db.session.get(ConnectedAccount, account)
    if account is None:
        return {"ok": False, "message": "Account not found."}
    if not account.sync_enabled:
        return {"ok": True, "account": serialize_account(account), "seen": 0, "imported": 0, "message": "Sync disabled."}

    try:
        from googleapiclient.discovery import build
        credentials = credentials_for_account(account)
        if credentials is None:
            raise RuntimeError("OAuth token is missing.")
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        message_ids = _gmail_message_ids(service, account, limit)
        imported = 0
        for provider_message_id in message_ids:
            message = service.users().messages().get(userId="me", id=provider_message_id, format="full").execute()
            imported += int(upsert_gmail_message(account, message))
        account.last_sync_at = datetime.utcnow()
        account.last_error = None
        db.session.commit()
        return {"ok": True, "account": serialize_account(account), "seen": len(message_ids), "imported": imported}
    except Exception as exc:
        LOGGER.warning("Gmail sync failed for account_id=%s: %s", account.id, exc)
        error = _friendly_sync_error(exc)
        account.last_error = error["message"]
    db.session.commit()
    return {
        "ok": False,
        "account": serialize_account(account),
        "seen": 0,
        "imported": 0,
        **error,
    }


def _gmail_message_ids(service, account, limit):
    found = []
    seen = set()
    if account.sync_cursor:
        try:
            page_token = None
            newest_history_id = account.sync_cursor
            while len(found) < limit:
                kwargs = {
                    "userId": "me",
                    "startHistoryId": account.sync_cursor,
                    "historyTypes": ["messageAdded", "labelAdded", "labelRemoved"],
                    "maxResults": min(500, limit),
                }
                if page_token:
                    kwargs["pageToken"] = page_token
                history = service.users().history().list(**kwargs).execute()
                for item in history.get("history", []):
                    for change in (
                        item.get("messagesAdded", [])
                        + item.get("labelsAdded", [])
                        + item.get("labelsRemoved", [])
                    ):
                        message_id = change.get("message", {}).get("id")
                        if message_id and message_id not in seen:
                            seen.add(message_id)
                            found.append(message_id)
                            if len(found) >= limit:
                                break
                newest_history_id = str(history.get("historyId") or newest_history_id)
                page_token = history.get("nextPageToken")
                if not page_token:
                    break
            account.sync_cursor = newest_history_id
            return found[:limit]
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status not in {404, None}:
                raise
            account.sync_cursor = None

    page_token = None
    while len(found) < limit:
        kwargs = {
            "userId": "me",
            "maxResults": min(100, limit - len(found)),
            "includeSpamTrash": False,
        }
        if page_token:
            kwargs["pageToken"] = page_token
        response = service.users().messages().list(**kwargs).execute()
        for item in response.get("messages", []):
            if item["id"] not in seen:
                seen.add(item["id"])
                found.append(item["id"])
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return found[:limit]


def upsert_gmail_message(account, raw):
    provider_message_id = raw.get("id")
    if not provider_message_id:
        return False
    existing = EmailMessage.query.filter_by(account_id=account.id, provider_message_id=provider_message_id).first()
    payload = raw.get("payload", {})
    headers = {item.get("name", "").lower(): item.get("value", "") for item in payload.get("headers", [])}
    subject = headers.get("subject", "")
    sent_at = _parse_gmail_date(headers.get("date"), raw.get("internalDate"))
    labels = raw.get("labelIds", [])
    body_text = _plain_text_from_payload(payload)
    provider_thread_id = raw.get("threadId", "")

    thread = EmailThread.query.filter_by(account_id=account.id, provider_thread_id=provider_thread_id).first()
    if thread is None:
        thread = EmailThread(account=account, provider_thread_id=provider_thread_id)
        db.session.add(thread)
        db.session.flush()
    thread.subject = thread.subject or subject
    thread.last_message_at = max(filter(None, [thread.last_message_at, sent_at]), default=sent_at)
    thread.labels_json = _dump(sorted(set(_json(thread.labels_json) + labels)))

    message = existing or EmailMessage(account=account, provider_message_id=provider_message_id)
    message.thread = thread
    message.provider_thread_id = provider_thread_id
    message.history_id = str(raw.get("historyId") or "")
    message.sender = headers.get("from", "")
    message.recipients_json = _dump([headers.get("to", ""), headers.get("cc", ""), headers.get("bcc", "")])
    message.subject = subject
    message.snippet = raw.get("snippet", "")
    message.body_text = body_text
    message.labels_json = _dump(labels)
    message.is_unread = "UNREAD" in labels
    message.sent_at = sent_at
    db.session.add(message)
    db.session.flush()

    if raw.get("historyId"):
        incoming_cursor = str(raw["historyId"])
        try:
            account.sync_cursor = str(max(int(account.sync_cursor or 0), int(incoming_cursor)))
        except ValueError:
            account.sync_cursor = incoming_cursor
    if existing is None:
        for attachment in _attachments_from_payload(payload):
            db.session.add(EmailAttachment(email=message, **attachment))
    return existing is None


def _plain_text_from_payload(payload):
    chunks = []

    def visit(part):
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if mime_type == "text/plain" and data:
            try:
                chunks.append(base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace"))
            except Exception:
                pass
        for child in part.get("parts", []) or []:
            visit(child)

    visit(payload)
    return "\n".join(chunks).strip()[:20000]


def _attachments_from_payload(payload):
    attachments = []

    def visit(part):
        filename = part.get("filename") or ""
        body = part.get("body", {})
        if filename:
            attachments.append(
                {
                    "filename": filename[:260],
                    "mime_type": part.get("mimeType", "")[:160],
                    "size_bytes": int(body.get("size") or 0),
                    "provider_attachment_id": body.get("attachmentId", ""),
                }
            )
        for child in part.get("parts", []) or []:
            visit(child)

    visit(payload)
    return attachments


def _parse_gmail_date(header_date, internal_date):
    if header_date:
        try:
            return parsedate_to_datetime(header_date).replace(tzinfo=None)
        except Exception:
            pass
    if internal_date:
        return datetime.fromtimestamp(int(internal_date) / 1000)
    return datetime.utcnow()


def analyze_pending_emails(limit=25, app_config=None):
    app_config = app_config or {}
    pending = EmailMessage.query.filter(EmailMessage.analyzed_at.is_(None)).order_by(EmailMessage.sent_at.desc()).limit(limit).all()
    analyzed = 0
    for email in pending:
        upsert_email_insight(email, analyze_email(email, app_config))
        analyzed += 1
    db.session.commit()
    return {"ok": True, "analyzed": analyzed}


def sync_account_intelligence(account, app_config=None, limit=50):
    sync = sync_account(account, limit=limit)
    if not sync.get("ok"):
        return sync
    analysis = analyze_pending_emails(limit=limit, app_config=app_config or {})
    from app.services.email_views import materialize_email_views

    views = materialize_email_views(limit=100)
    return {
        **sync,
        "analysis": analysis,
        "views": views,
        "message": (
            f"Gmail sync finished: {sync.get('imported', 0)} new messages, "
            f"{analysis['analyzed']} analyzed, {views['opportunities']} opportunities, "
            f"and {views['reminders']} reminders added."
        ),
    }


def analyze_email(email, app_config):
    prompt = (
        "Return compact JSON for this email. No markdown. "
        "Use category only from: internship, hackathon, meeting, assignment, reminder, finance, travel, shopping, learning, personal, general. "
        "Include priority, urgency, category, summary, action_items, deadlines, meetings, follow_ups, waiting_on, "
        "projects, people, companies, required_documents, repositories, suggested_actions, confidence.\n"
        f"From: {email.sender}\nSubject: {email.subject}\nSnippet: {email.snippet}\nBody: {(email.body_text or '')[:3500]}"
    )
    response = ollama_generate_json(prompt, app_config)
    if response:
        return normalize_insight(response)
    return heuristic_insight(email)


def ollama_generate_json(prompt, app_config):
    if app_config.get("AI_PROVIDER", "ollama") not in {"ollama", "local", ""}:
        return None
    base_url = (app_config.get("OLLAMA_URL") or "http://localhost:11434").rstrip("/")
    model = app_config.get("OLLAMA_MODEL") or "qwen2.5:3b"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json"}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
            return json.loads(data.get("response", "{}"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None


def normalize_insight(raw):
    category = str(raw.get("category") or "general").lower().strip()
    category = category if category in EMAIL_CATEGORIES else "general"
    return {
        "priority": str(raw.get("priority") or "normal").lower()[:40],
        "urgency": str(raw.get("urgency") or "normal").lower()[:40],
        "category": category,
        "summary": str(raw.get("summary") or "")[:1000],
        "action_items": _as_list(raw.get("action_items")),
        "deadlines": _as_list(raw.get("deadlines")),
        "meetings": _as_list(raw.get("meetings")),
        "follow_ups": _as_list(raw.get("follow_ups")),
        "waiting_on": _as_list(raw.get("waiting_on")),
        "projects": _as_list(raw.get("projects")),
        "people": _as_list(raw.get("people")),
        "companies": _as_list(raw.get("companies")),
        "required_documents": _as_list(raw.get("required_documents")),
        "repositories": _as_list(raw.get("repositories")),
        "suggested_actions": _as_list(raw.get("suggested_actions")),
        "confidence": float(raw.get("confidence") or 0.75),
    }


def heuristic_insight(email):
    full_text = f"{email.subject} {email.snippet} {email.body_text or ''}"
    text = full_text.lower()
    urgent = any(word in text for word in ["urgent", "asap", "today", "deadline", "by friday", "tomorrow"])
    action = any(word in text for word in ["can you", "please", "finish", "send", "review", "submit"])
    deadlines = extract_deadlines(text)
    meetings = [email.subject] if any(word in text for word in ["meeting", "call", "zoom", "google meet", "interview"]) else []
    category = classify_email_text(text)
    required_documents = extract_required_documents(text)
    repositories = extract_repositories(full_text)
    projects = extract_projects(email.subject, full_text)
    people = extract_people(email.sender, full_text)
    companies = sorted(set(extract_companies(email.sender) + extract_known_companies(full_text)))
    suggested_actions = suggest_email_actions(email, category, action, deadlines, required_documents, meetings)
    return {
        "priority": "high" if urgent or deadlines else "normal",
        "urgency": "urgent" if urgent else "normal",
        "category": category,
        "summary": email.snippet or email.subject,
        "action_items": [email.subject] if action else [],
        "deadlines": deadlines,
        "meetings": meetings,
        "follow_ups": [email.sender] if "follow up" in text else [],
        "waiting_on": [],
        "projects": projects,
        "people": people,
        "companies": companies,
        "required_documents": required_documents,
        "repositories": repositories,
        "suggested_actions": suggested_actions,
        "confidence": 0.58,
    }


def classify_email_text(text):
    rules = [
        ("internship", ["internship", "intern ", "interview", "recruiter", "application", "placement", "offer letter"]),
        ("hackathon", ["hackathon", "devpost", "buildathon", "challenge", "submission", "demo video"]),
        ("meeting", ["meeting", "calendar invite", "zoom", "google meet", "call", "interview schedule"]),
        ("assignment", ["assignment", "homework", "coursework", "submit", "submission", "due date"]),
        ("reminder", ["reminder", "don't forget", "do not forget", "follow up", "following up"]),
        ("finance", ["invoice", "payment", "bank", "refund", "salary", "tax", "receipt"]),
        ("travel", ["flight", "hotel", "booking", "boarding", "ticket", "trip", "itinerary"]),
        ("shopping", ["order", "delivery", "shipped", "cart", "purchase", "tracking number"]),
        ("learning", ["course", "lecture", "tutorial", "lesson", "module", "workshop", "webinar"]),
        ("personal", ["family", "personal", "birthday", "appointment"]),
    ]
    for category, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return category
    return "general"


def extract_deadlines(text):
    found = []
    for pattern in [r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", r"\b(today|tomorrow)\b", r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"]:
        found.extend(match.group(0) for match in re.finditer(pattern, text, re.I))
    return found[:5]


def extract_required_documents(text):
    docs = []
    patterns = {
        "resume": ["resume", "cv"],
        "transcript": ["transcript", "marksheet", "grade sheet"],
        "portfolio": ["portfolio"],
        "cover letter": ["cover letter"],
        "id proof": ["id proof", "identity proof", "government id"],
        "certificate": ["certificate", "certification"],
    }
    for label, keywords in patterns.items():
        if any(keyword in text for keyword in keywords):
            docs.append(label)
    return docs[:8]


def extract_repositories(text):
    repos = []
    for match in re.finditer(r"https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text):
        repos.append(match.group(0).rstrip(").,"))
    for match in re.finditer(r"\brepo(?:sitory)?[:\s]+(https?://\S+)", text, re.I):
        repos.append(match.group(1).rstrip(").,"))
    return list(dict.fromkeys(repos))[:6]


def extract_projects(subject, text):
    projects = extract_title_words(subject)
    for pattern in [r"\bproject[:\s]+([A-Z][A-Za-z0-9 _-]{2,40})", r"\bfor\s+([A-Z][A-Za-z0-9_-]{2,30})\b"]:
        for match in re.finditer(pattern, text):
            projects.append(match.group(1).strip())
    return list(dict.fromkeys(projects))[:8]


def extract_title_words(subject):
    words = [word.strip(":-|[]()") for word in re.split(r"\s+", subject) if len(word) > 3 and word[:1].isupper()]
    return words[:4]


def extract_companies(sender):
    match = re.search(r"@([a-z0-9-]+)\.", sender.lower())
    return [match.group(1).title()] if match else []


def extract_known_companies(text):
    companies = []
    for match in re.finditer(r"\b(Amazon|Google|Microsoft|Meta|Apple|Netflix|OpenAI|GitHub|LinkedIn|Flipkart|TCS|Infosys|Wipro)\b", text):
        companies.append(match.group(1))
    return companies[:8]


def extract_people(sender, text):
    people = []
    display_name, email_address = parseaddr(sender or "")
    if display_name and "@" not in display_name:
        people.append(display_name.strip('" '))
    elif email_address:
        local_part = email_address.split("@", 1)[0].replace(".", " ").replace("_", " ")
        if local_part and not any(char.isdigit() for char in local_part):
            people.append(local_part.title())

    for pattern in [r"\b(?:with|from|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:asked|sent|shared|scheduled)\b"]:
        for match in re.finditer(pattern, text):
            people.append(match.group(1).strip())
    return list(dict.fromkeys(people))[:8]


def suggest_email_actions(email, category, has_action, deadlines, required_documents, meetings):
    suggestions = []
    if required_documents:
        suggestions.append(f"Collect required documents: {', '.join(required_documents)}")
    if category == "internship":
        suggestions.append(f"Review internship email: {email.subject}")
    if category == "hackathon":
        suggestions.append(f"Plan hackathon next step: {email.subject}")
    if meetings:
        suggestions.append(f"Prepare for meeting: {email.subject}")
    if deadlines:
        suggestions.append(f"Schedule work before {deadlines[0]}")
    if has_action and not suggestions:
        suggestions.append(email.subject)
    return suggestions[:8]


def _as_list(value):
    if isinstance(value, list):
        return [str(item)[:300] for item in value if str(item).strip()][:10]
    if isinstance(value, str) and value.strip():
        return [value.strip()[:300]]
    return []


def upsert_email_insight(email, insight):
    row = email.insight or EmailInsight(email=email)
    row.priority = insight["priority"]
    row.urgency = insight["urgency"]
    row.category = insight["category"]
    row.summary = insight["summary"]
    row.action_items_json = _dump(insight["action_items"])
    row.deadlines_json = _dump(insight["deadlines"])
    row.meetings_json = _dump(insight["meetings"])
    row.follow_ups_json = _dump(insight["follow_ups"])
    row.waiting_on_json = _dump(insight["waiting_on"])
    row.projects_json = _dump(insight["projects"])
    row.people_json = _dump(insight["people"])
    row.companies_json = _dump(insight["companies"])
    row.required_documents_json = _dump(insight["required_documents"])
    row.repositories_json = _dump(insight["repositories"])
    row.suggested_actions_json = _dump(insight["suggested_actions"])
    row.model = "ollama_or_rule_based"
    row.confidence = insight["confidence"]
    email.analyzed_at = datetime.utcnow()
    db.session.add(row)
    due_at = first_deadline_datetime(insight["deadlines"], email.sent_at or datetime.utcnow())
    for title in list(dict.fromkeys(insight["action_items"] + insight["suggested_actions"])):
        if not EmailTask.query.filter_by(email=email, title=title).first():
            db.session.add(EmailTask(email=email, title=title, priority=row.priority, due_at=due_at, source="email_insight"))
    life_item = upsert_life_item_from_email(email, insight, due_at)
    if life_item:
        row.life_item = life_item
    return row


def upsert_life_item_from_email(email, insight, due_at=None):
    if not is_important_email(insight):
        return None

    source_key = f"email:{email.account_id}:{email.provider_message_id}"
    item = LifeItem.query.filter_by(source_key=source_key).first()
    if item is None:
        item = LifeItem(source_key=source_key)
        db.session.add(item)

    labels = _json(email.labels_json)
    next_action = first_non_empty(insight["suggested_actions"] + insight["action_items"]) or f"Review email: {email.subject}"
    item.title = make_life_item_title(email, insight, next_action)
    item.description = (insight["summary"] or email.snippet or email.body_text or "")[:2500]
    item.category = insight["category"] if insight["category"] != "general" else "personal"
    item.priority = insight["priority"]
    item.status = "open"
    item.deadline = due_at
    item.estimated_hours = estimate_life_item_hours(insight)
    item.progress = item.progress or 0.0
    item.energy_level = "high" if insight["priority"] in {"high", "urgent"} else "medium"
    item.difficulty = "medium"
    item.repository = first_non_empty(insight["repositories"])
    item.ai_summary = insight["summary"]
    item.next_action = next_action
    item.tags_json = _dump(sorted(set(labels + [insight["category"]] + insight["projects"] + insight["companies"])))
    item.analytics_json = _dump_object({"source": "email_intelligence", "confidence": insight["confidence"]})
    item.metadata_json = _dump_object(
        {
            "email_id": email.id,
            "account_id": email.account_id,
            "provider_message_id": email.provider_message_id,
            "provider_thread_id": email.provider_thread_id,
            "thread_id": email.thread_id,
            "sender": email.sender,
            "labels": labels,
            "required_documents": insight["required_documents"],
            "meetings": insight["meetings"],
            "people": insight["people"],
            "companies": insight["companies"],
            "projects": insight["projects"],
            "repositories": insight["repositories"],
        }
    )
    history = _json(item.history_json)
    history.append({"at": datetime.utcnow().isoformat(), "event": "email_insight_updated", "email_id": email.id})
    item.history_json = _dump(history[-20:])
    db.session.flush()
    connect_related_life_items(item, insight)
    return item


def is_important_email(insight):
    return any(
        [
            insight["priority"] in {"high", "urgent"},
            insight["urgency"] in {"high", "urgent"},
            insight["category"] in IMPORTANT_CATEGORIES,
            bool(insight["deadlines"]),
            bool(insight["action_items"]),
            bool(insight["suggested_actions"]),
        ]
    )


def make_life_item_title(email, insight, next_action):
    if insight["category"] == "meeting" and insight["meetings"]:
        return f"Meeting: {email.subject}"[:240]
    if insight["category"] == "internship":
        company = first_non_empty(insight["companies"])
        return f"Internship: {company or email.subject}"[:240]
    if insight["category"] == "hackathon":
        project = first_non_empty(insight["projects"])
        return f"Hackathon: {project or email.subject}"[:240]
    return (next_action or email.subject or "Email follow-up")[:240]


def estimate_life_item_hours(insight):
    if insight["category"] in {"meeting", "reminder"}:
        return 0.5
    if insight["category"] in {"hackathon", "assignment", "learning"}:
        return 2.0
    if insight["required_documents"]:
        return 1.0
    return 0.75


def connect_related_life_items(item, insight):
    signals = {value.lower() for value in insight["projects"] + insight["companies"] if value}
    repo = first_non_empty(insight["repositories"])
    if repo:
        signals.add(repo.lower())
    candidates = LifeItem.query.filter(LifeItem.id != item.id).limit(200).all()
    for candidate in candidates:
        haystack = " ".join(
            [
                candidate.title or "",
                candidate.description or "",
                candidate.repository or "",
                candidate.tags_json or "",
                candidate.metadata_json or "",
            ]
        ).lower()
        matched = [signal for signal in signals if signal and signal in haystack]
        if not matched:
            continue
        exists = LifeItemRelation.query.filter_by(
            source_item_id=item.id,
            target_item_id=candidate.id,
            relation_type="email_context",
        ).first()
        if exists:
            continue
        db.session.add(
            LifeItemRelation(
                source_item=item,
                target_item=candidate,
                relation_type="email_context",
                strength=min(1.0, 0.55 + 0.1 * len(matched)),
                reason=f"Email mentions shared context: {', '.join(matched[:3])}",
                metadata_json=_dump_object({"signals": matched[:6]}),
            )
        )


def first_non_empty(values):
    for value in values or []:
        if str(value).strip():
            return str(value).strip()
    return None


def first_deadline_datetime(deadlines, anchor=None):
    anchor = anchor or datetime.utcnow()
    for deadline in deadlines or []:
        parsed = parse_deadline_text(str(deadline), anchor)
        if parsed:
            return parsed
    return None


def parse_deadline_text(value, anchor=None):
    anchor = anchor or datetime.utcnow()
    text = value.strip().lower()
    if not text:
        return None
    if "today" in text:
        return datetime.combine(anchor.date(), datetime.min.time()).replace(hour=17)
    if "tomorrow" in text:
        return datetime.combine(anchor.date() + timedelta(days=1), datetime.min.time()).replace(hour=17)
    weekday_match = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)
    if weekday_match:
        weekday = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].index(weekday_match.group(1))
        days_ahead = (weekday - anchor.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return datetime.combine(anchor.date() + timedelta(days=days_ahead), datetime.min.time()).replace(hour=17)
    numeric_match = re.search(r"\b(?P<month>\d{1,2})[/-](?P<day>\d{1,2})(?:[/-](?P<year>\d{2,4}))?\b", text)
    if numeric_match:
        month = int(numeric_match.group("month"))
        day = int(numeric_match.group("day"))
        year_raw = numeric_match.group("year")
        year = anchor.year if not year_raw else int(year_raw)
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day, 17)
        except ValueError:
            return None
    return None


def generate_daily_plan(plan_date=None):
    plan_date = plan_date or date.today()
    urgent = (
        EmailInsight.query.join(EmailMessage)
        .filter(EmailInsight.priority.in_(["high", "urgent"]))
        .order_by(EmailMessage.sent_at.desc())
        .limit(8)
        .all()
    )
    open_tasks = EmailTask.query.filter_by(status="open").order_by(EmailTask.created_at.desc()).limit(8).all()
    items = []
    hour = 8
    minute = 30
    for insight in urgent[:4]:
        items.append({"time": f"{hour:02d}:{minute:02d}", "title": insight.summary or insight.email.subject, "duration_minutes": 30, "source": "urgent_email"})
        hour += 1
    for task in open_tasks[:4]:
        items.append({"time": f"{hour:02d}:{minute:02d}", "title": task.title, "duration_minutes": task.estimated_minutes if hasattr(task, "estimated_minutes") else 45, "source": "email_task"})
        hour += 1
    if not items:
        items.append({"time": "09:00", "title": "Review inbox and choose one deep-work block", "duration_minutes": 45, "source": "fallback"})
    row = DailyPlan.query.filter_by(plan_date=plan_date).first() or DailyPlan(plan_date=plan_date, items_json="[]")
    row.summary = f"{len(urgent)} urgent email signals and {len(open_tasks)} open email tasks."
    row.items_json = _dump(items)
    db.session.add(row)
    db.session.commit()
    return serialize_daily_plan(row)


def generate_weekly_plan(week_start=None):
    today = date.today()
    week_start = week_start or (today - timedelta(days=today.weekday()))
    items = [
        {"day": "Monday", "focus": "Email triage and project planning"},
        {"day": "Tuesday", "focus": "Deep work and coding"},
        {"day": "Wednesday", "focus": "Meetings and follow-ups"},
        {"day": "Thursday", "focus": "Applications, reviews, and deadlines"},
        {"day": "Friday", "focus": "Weekly review and cleanup"},
    ]
    row = WeeklyPlan.query.filter_by(week_start=week_start).first() or WeeklyPlan(week_start=week_start, items_json="[]")
    row.summary = "Local weekly plan generated from email urgency, open tasks, and deadlines."
    row.items_json = _dump(items)
    db.session.add(row)
    db.session.commit()
    return serialize_weekly_plan(row)


def refresh_suggestions():
    stale_cutoff = datetime.utcnow() - timedelta(days=3)
    candidates = (
        EmailMessage.query.filter(EmailMessage.sent_at <= stale_cutoff)
        .filter(EmailMessage.analyzed_at.isnot(None))
        .order_by(EmailMessage.sent_at.desc())
        .limit(20)
        .all()
    )
    created = 0
    for email in candidates:
        title = f"Check follow-up: {email.subject[:140]}"
        if not AISuggestion.query.filter_by(title=title, status="open").first():
            db.session.add(AISuggestion(kind="follow_up", title=title, details=f"Unanswered or old thread from {email.sender}."))
            created += 1
    db.session.commit()
    return {"ok": True, "created": created}


def intelligence_today():
    daily = DailyPlan.query.filter_by(plan_date=date.today()).first()
    if daily is None:
        return generate_daily_plan()
    return serialize_daily_plan(daily)


def intelligence_summary():
    from app.services.daily_assistant import latest_daily_assistant_summary
    from app.services.planning_events import planning_board
    from app.services.github_intelligence import generate_daily_summary, serialize_daily_summary
    from app.services.learning_intelligence import learning_summary
    from app.services.college_intelligence import pat_college_summary
    from app.services.project_context import project_context

    urgent = EmailInsight.query.filter(EmailInsight.priority.in_(["high", "urgent"])).count()
    unread = EmailMessage.query.filter_by(is_unread=True).count()
    accounts = ConnectedAccount.query.count()
    daily = intelligence_today()
    weekly = WeeklyPlan.query.order_by(WeeklyPlan.week_start.desc()).first()
    suggestions = AISuggestion.query.filter_by(status="open").order_by(AISuggestion.created_at.desc()).limit(6).all()
    deadlines = EmailInsight.query.filter(EmailInsight.deadlines_json != "[]").order_by(EmailInsight.updated_at.desc()).limit(6).all()
    waiting = EmailInsight.query.filter(EmailInsight.waiting_on_json != "[]").order_by(EmailInsight.updated_at.desc()).limit(6).all()
    learning = learning_summary()
    events = planning_board()
    github_daily = generate_daily_summary()
    db.session.commit()
    return {
        "accounts": accounts,
        "unread_emails": unread,
        "urgent_emails": urgent,
        "assistant": latest_daily_assistant_summary(),
        "today": daily,
        "weekly": serialize_weekly_plan(weekly) if weekly else generate_weekly_plan(),
        "github": serialize_daily_summary(github_daily),
        "learning": learning,
        "planning_events": events,
        "projects": project_context(),
        "college": pat_college_summary(),
        "suggestions": [serialize_suggestion(item) for item in suggestions],
        "deadlines": [serialize_insight(item) for item in deadlines],
        "waiting_for": [serialize_insight(item) for item in waiting],
    }


def semantic_search(query, limit=8):
    query_l = query.lower()
    rows = EmailMessage.query.order_by(EmailMessage.sent_at.desc()).limit(300).all()
    scored = []
    for email in rows:
        text = f"{email.subject} {email.sender} {email.snippet} {email.body_text or ''}".lower()
        score = sum(text.count(term) for term in query_l.split() if len(term) > 2)
        if score:
            scored.append((score, email))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [serialize_email(email) for _score, email in scored[:limit]]


def serialize_email(email):
    return {
        "id": email.id,
        "account": email.account.email if email.account else "",
        "sender": email.sender or "",
        "subject": email.subject,
        "timestamp": email.sent_at.isoformat() if email.sent_at else None,
        "labels": _json(email.labels_json),
        "snippet": email.snippet or "",
        "insight": serialize_insight(email.insight) if email.insight else None,
    }


def serialize_insight(insight):
    return {
        "email_id": insight.email_id,
        "life_item_id": insight.life_item_id,
        "subject": insight.email.subject if insight.email else "",
        "sender": insight.email.sender if insight.email else "",
        "priority": insight.priority,
        "urgency": insight.urgency,
        "category": insight.category,
        "summary": insight.summary or "",
        "action_items": _json(insight.action_items_json),
        "deadlines": _json(insight.deadlines_json),
        "meetings": _json(insight.meetings_json),
        "waiting_on": _json(insight.waiting_on_json),
        "projects": _json(insight.projects_json),
        "companies": _json(insight.companies_json),
        "people": _json(insight.people_json),
        "required_documents": _json(insight.required_documents_json),
        "repositories": _json(insight.repositories_json),
        "suggested_actions": _json(insight.suggested_actions_json),
    }


def serialize_daily_plan(row):
    return {"date": row.plan_date.isoformat(), "summary": row.summary or "", "items": _json(row.items_json)}


def serialize_weekly_plan(row):
    return {"week_start": row.week_start.isoformat(), "summary": row.summary or "", "items": _json(row.items_json)}


def serialize_suggestion(row):
    return {"id": row.id, "kind": row.kind, "title": row.title, "details": row.details or "", "created_at": row.created_at.isoformat()}


def run_email_intelligence_cycle(app_config):
    from app.services.daily_assistant import latest_daily_assistant_summary
    from app.services.github_intelligence import update_all_repositories
    from app.services.learning_intelligence import generate_events_from_learning_items, learning_summary
    from app.services.planning_events import planning_board
    from app.services.email_views import materialize_email_views

    sync_results = sync_all_accounts(limit_per_account=30)
    analysis = analyze_pending_emails(limit=30, app_config=app_config)
    views = materialize_email_views(limit=100)
    github = update_all_repositories(limit=30)
    generate_events_from_learning_items()
    daily = generate_daily_plan()
    weekly = generate_weekly_plan()
    suggestions = refresh_suggestions()
    planning = planning_board()
    return {
        "sync": sync_results,
        "analysis": analysis,
        "views": views,
        "assistant": latest_daily_assistant_summary(),
        "github": github,
        "learning": learning_summary(),
        "daily": daily,
        "weekly": weekly,
        "suggestions": suggestions,
        "planning": {
            "rows": planning["counts"]["total"],
            "today": planning["counts"]["today"],
            "week": planning["counts"]["week"],
            "month": planning["counts"]["month"],
            "questions": len(planning["question_queue"]),
        },
    }
