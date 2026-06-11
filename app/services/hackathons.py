import hashlib
import re
from datetime import datetime
from urllib.parse import urlparse

from app.models import HackathonUpdate, Opportunity, db


PLATFORM_DOMAINS = {
    "unstop.com": "unstop",
    "hack2skill.com": "hack2skill",
    "hackerearth.com": "hackerearth",
    "devfolio.co": "devfolio",
    "devpost.com": "devpost",
}

STATUS_MAP = {
    "registration": "Applied",
    "applied": "Applied",
    "shortlisted": "Shortlisted",
    "qualified": "Shortlisted",
    "team": "Team update",
    "submission": "Submission due",
    "deadline": "Deadline",
    "submitted": "Submitted",
    "result": "Result",
    "winner": "Result",
    "rejected": "Closed",
}


def ingest_hackathon_signal(
    *,
    title,
    source,
    body="",
    organization="",
    platform="",
    url="",
    status="",
    deadline=None,
    external_id="",
    occurred_at=None,
):
    clean_title = clean_text(title, 180) or "Untitled hackathon"
    clean_body = clean_text(body, 4000)
    detected_platform = normalize_platform(platform or detect_platform(source, organization, url, clean_body))
    detected_status = normalize_status(status or detect_status(f"{clean_title} {clean_body}"))
    parsed_deadline = parse_optional_datetime(deadline) or detect_deadline(clean_body)
    organizer = clean_text(organization, 120) or detected_platform.title()
    opportunity = find_hackathon(clean_title, organizer, detected_platform)

    if opportunity is None:
        opportunity = Opportunity(
            kind="hackathon",
            title=clean_title,
            organization=organizer,
            status=detected_status,
            source=clean_text(source, 80),
            deadline=parsed_deadline,
            notes=clean_body[:1200],
        )
        db.session.add(opportunity)
        db.session.flush()
    else:
        opportunity.status = choose_status(opportunity.status, detected_status)
        opportunity.deadline = parsed_deadline or opportunity.deadline
        opportunity.notes = clean_body[:1200] or opportunity.notes
        opportunity.source = clean_text(source, 80) or opportunity.source
        opportunity.updated_at = datetime.utcnow()

    signal_id = external_id or build_external_id(detected_platform, source, clean_title, clean_body)
    existing_update = HackathonUpdate.query.filter_by(external_id=signal_id).first()

    if existing_update:
        return opportunity, existing_update, False

    update = HackathonUpdate(
        opportunity=opportunity,
        platform=detected_platform,
        source=clean_text(source, 180) or detected_platform,
        external_id=signal_id,
        event_type=detect_event_type(f"{clean_title} {clean_body}"),
        title=clean_title,
        summary=clean_body[:1200],
        action_needed=build_action_needed(detected_status, parsed_deadline),
        deadline=parsed_deadline,
        occurred_at=parse_optional_datetime(occurred_at),
    )
    db.session.add(update)
    return opportunity, update, True


def serialize_hackathon(opportunity):
    updates = sorted(
        opportunity.hackathon_updates,
        key=lambda item: item.occurred_at or item.created_at,
        reverse=True,
    )
    platform = updates[0].platform if updates else detect_platform(opportunity.source, opportunity.organization)

    return {
        "id": opportunity.id,
        "title": opportunity.title,
        "organizer": opportunity.organization or "",
        "platform": normalize_platform(platform),
        "status": opportunity.status,
        "source": opportunity.source or "",
        "deadline": opportunity.deadline.isoformat() if opportunity.deadline else None,
        "notes": opportunity.notes or "",
        "unread_updates": sum(1 for item in updates if not item.is_read),
        "updated_at": opportunity.updated_at.isoformat(),
        "updates": [serialize_hackathon_update(item) for item in updates[:12]],
    }


def serialize_hackathon_update(item):
    return {
        "id": item.id,
        "platform": item.platform,
        "source": item.source,
        "event_type": item.event_type,
        "title": item.title,
        "summary": item.summary or "",
        "action_needed": item.action_needed or "",
        "deadline": item.deadline.isoformat() if item.deadline else None,
        "is_read": item.is_read,
        "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
        "created_at": item.created_at.isoformat(),
    }


def find_hackathon(title, organization, platform):
    normalized_title = normalize_match_text(title)
    candidates = Opportunity.query.filter_by(kind="hackathon").all()

    for candidate in candidates:
        candidate_title = normalize_match_text(candidate.title)
        same_title = normalized_title == candidate_title
        title_contains = len(normalized_title) >= 8 and (
            normalized_title in candidate_title or candidate_title in normalized_title
        )
        same_organizer = normalize_match_text(candidate.organization) == normalize_match_text(organization)
        same_platform = platform in normalize_match_text(candidate.source)

        if same_title or (title_contains and (same_organizer or same_platform)):
            return candidate

    return None


def detect_platform(*values):
    text = " ".join(str(value or "") for value in values).lower()
    for domain, platform in PLATFORM_DOMAINS.items():
        if domain in text or platform in text:
            return platform
    return "other"


def normalize_platform(value):
    text = clean_text(value, 80).lower()
    for domain, platform in PLATFORM_DOMAINS.items():
        if domain in text or platform in text:
            return platform
    return text or "other"


def detect_status(text):
    lowered = text.lower()
    for keyword, status in STATUS_MAP.items():
        if keyword in lowered:
            return status
    return "Tracked"


def normalize_status(value):
    clean_value = clean_text(value, 60)
    return STATUS_MAP.get(clean_value.lower(), clean_value or "Tracked")


def choose_status(current, incoming):
    rank = {
        "Tracked": 0,
        "Applied": 1,
        "Shortlisted": 2,
        "Team update": 2,
        "Deadline": 3,
        "Submission due": 3,
        "Submitted": 4,
        "Result": 5,
        "Closed": 5,
    }
    return incoming if rank.get(incoming, 0) >= rank.get(current, 0) else current


def detect_event_type(text):
    lowered = text.lower()
    for event_type, keywords in (
        ("result", ("result", "winner", "selected", "shortlisted", "qualified")),
        ("submission", ("submission", "submit", "prototype", "pitch deck")),
        ("deadline", ("deadline", "due date", "last date")),
        ("registration", ("registration", "application received", "successfully registered")),
        ("team", ("team", "invite", "member")),
    ):
        if any(keyword in lowered for keyword in keywords):
            return event_type
    return "update"


def detect_deadline(text):
    iso_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if iso_match:
        return parse_optional_datetime("-".join(iso_match.groups()))
    return None


def build_action_needed(status, deadline):
    if status in {"Deadline", "Submission due"}:
        suffix = f" before {deadline.strftime('%d %b %Y')}" if deadline else ""
        return f"Review the submission requirements and finish the next milestone{suffix}."
    if status == "Shortlisted":
        return "Open the platform, confirm the next round, and update the build plan."
    if status == "Applied":
        return "Verify the application details and watch for shortlist or team updates."
    if status == "Result":
        return "Review the result and save any certificate, feedback, or next-step details."
    return "Review this update and adjust the hackathon plan if needed."


def build_external_id(platform, source, title, body):
    raw = "\n".join((platform, str(source or ""), title, body[:1000]))
    return f"signal:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def parse_optional_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None

    cleaned = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError:
        return None


def clean_text(value, limit):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize_match_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def platform_from_url(url):
    try:
        return detect_platform(urlparse(url).hostname or "")
    except ValueError:
        return "other"
