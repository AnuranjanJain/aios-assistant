import csv
import json
import mailbox
from email import policy
from email.parser import BytesParser
from pathlib import Path

from app.services.agent_ingest import ingest_message


SUPPORTED_IMPORTS = {".eml", ".mbox", ".json", ".csv"}


def import_source_file(path, classifier, provider, model=None, limit=100):
    suffix = Path(path).suffix.lower()
    if suffix not in SUPPORTED_IMPORTS:
        raise ValueError(f"Unsupported file type: {suffix}")

    if suffix == ".eml":
        messages = [parse_eml(path)]
    elif suffix == ".mbox":
        messages = parse_mbox(path, limit=limit)
    elif suffix == ".json":
        messages = parse_json(path, limit=limit)
    else:
        messages = parse_csv(path, limit=limit)

    imported = []
    for message in messages[:limit]:
        subject = clean_value(message.get("subject")) or "Untitled imported message"
        imported.append(
            ingest_message(
                sender=clean_value(message.get("sender")),
                subject=subject,
                body=clean_value(message.get("body")),
                source=f"file import: {Path(path).name}",
                classifier=classifier,
                provider=provider,
                model=model,
            )
        )

    return imported


def parse_eml(path):
    with open(path, "rb") as file:
        message = BytesParser(policy=policy.default).parse(file)

    return {
        "sender": message.get("from", ""),
        "subject": message.get("subject", ""),
        "body": extract_email_body(message),
    }


def parse_mbox(path, limit=100):
    messages = []
    for index, message in enumerate(mailbox.mbox(path)):
        if index >= limit:
            break
        messages.append(
            {
                "sender": message.get("from", ""),
                "subject": message.get("subject", ""),
                "body": extract_email_body(message),
            }
        )
    return messages


def parse_json(path, limit=100):
    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    items = payload if isinstance(payload, list) else payload.get("messages", [])
    return [
        {
            "sender": item.get("sender") or item.get("from") or "",
            "subject": item.get("subject") or item.get("title") or "",
            "body": item.get("body") or item.get("content") or item.get("text") or "",
        }
        for item in items[:limit]
        if isinstance(item, dict)
    ]


def parse_csv(path, limit=100):
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = []
        for index, row in enumerate(reader):
            if index >= limit:
                break
            rows.append(
                {
                    "sender": row.get("sender") or row.get("from") or row.get("email") or "",
                    "subject": row.get("subject") or row.get("title") or "",
                    "body": row.get("body") or row.get("content") or row.get("notes") or "",
                }
            )
        return rows


def extract_email_body(message):
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                return safe_get_content(part)
        for part in message.walk():
            if part.get_content_type() == "text/html":
                return safe_get_content(part)

    return safe_get_content(message)


def safe_get_content(part):
    try:
        return part.get_content()
    except Exception:
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            return payload.decode("utf-8", errors="ignore")
        return str(payload or "")


def clean_value(value):
    return str(value or "").strip()
