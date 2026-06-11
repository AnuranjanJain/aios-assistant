import hashlib
import re
from datetime import datetime

from app.models import Opportunity, PlacementUpdate, db
from app.services.hackathons import clean_text, parse_optional_datetime


STATUS_RULES = (
    ("Rejected", ("unfortunately", "not moving forward", "not selected", "rejected", "rejection")),
    ("Offer", ("offer letter", "selected for", "congratulations", "pleased to offer")),
    ("Interview Scheduled", ("interview", "technical round", "hr round", "manager round")),
    ("OA Received", ("online assessment", "coding assessment", "assessment", "test link", "oa")),
    ("Shortlisted", ("shortlisted", "shortlist", "qualified", "next round")),
    ("Deadline", ("deadline", "due date", "last date", "complete by", "before")),
    ("Applied", ("application received", "thank you for applying", "successfully applied", "applied")),
    ("Opening", ("job opening", "hiring", "apply now", "applications open", "opening", "vacancy")),
)

EVENT_RULES = (
    ("rejection", ("unfortunately", "not moving forward", "not selected", "rejected", "rejection")),
    ("offer", ("offer letter", "pleased to offer", "congratulations")),
    ("interview", ("interview", "technical round", "hr round", "manager round")),
    ("assessment", ("online assessment", "coding assessment", "assessment", "test link", "oa")),
    ("shortlist", ("shortlisted", "shortlist", "qualified", "next round")),
    ("deadline", ("deadline", "due date", "last date", "complete by")),
    ("application", ("application received", "thank you for applying", "successfully applied", "applied")),
    ("opening", ("job opening", "hiring", "apply now", "applications open", "opening", "vacancy")),
)


def ingest_placement_signal(
    *,
    title,
    source,
    body="",
    organization="",
    status="",
    kind="job",
    deadline=None,
    external_id="",
    occurred_at=None,
):
    clean_title = clean_text(title, 180) or "Untitled placement update"
    clean_body = clean_text(body, 4000)
    company = clean_text(organization, 120) or detect_company(source, clean_title, clean_body) or "Unknown"
    opportunity_kind = "neopat" if kind == "neopat" or is_neopat_signal(clean_title, source, clean_body) else "job"
    detected_status = normalize_status(status or detect_status(f"{clean_title} {clean_body}"))
    parsed_deadline = parse_optional_datetime(deadline) or detect_deadline(clean_body)
    opportunity = find_placement(clean_title, company, opportunity_kind)

    if opportunity is None:
        opportunity = Opportunity(
            kind=opportunity_kind,
            title=clean_title,
            organization=company,
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

    signal_id = external_id or build_external_id(source, clean_title, clean_body)
    existing_update = PlacementUpdate.query.filter_by(external_id=signal_id).first()
    if existing_update:
        return opportunity, existing_update, False

    update = PlacementUpdate(
        opportunity=opportunity,
        source=clean_text(source, 180) or "local api",
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


def serialize_placement(opportunity):
    updates = sorted(
        opportunity.placement_updates,
        key=lambda item: item.occurred_at or item.created_at,
        reverse=True,
    )
    applied_at = detect_applied_at(opportunity, updates)
    latest_update_at = None
    if updates:
        latest_update_at = updates[0].occurred_at or updates[0].created_at

    return {
        "id": opportunity.id,
        "title": opportunity.title,
        "company": opportunity.organization or "",
        "status": opportunity.status,
        "category": opportunity.kind,
        "source": opportunity.source or "",
        "deadline": opportunity.deadline.isoformat() if opportunity.deadline else None,
        "applied_at": applied_at.isoformat() if applied_at else None,
        "received_at": latest_update_at.isoformat() if latest_update_at else opportunity.created_at.isoformat(),
        "notes": opportunity.notes or "",
        "unread_updates": sum(1 for item in updates if not item.is_read),
        "metrics": build_metrics(opportunity, updates, applied_at),
        "updated_at": opportunity.updated_at.isoformat(),
        "updates": [serialize_placement_update(item) for item in updates[:12]],
    }


def serialize_placement_update(item):
    return {
        "id": item.id,
        "source": item.source,
        "event_type": item.event_type,
        "title": item.title,
        "summary": item.summary or "",
        "action_needed": item.action_needed or "",
        "deadline": item.deadline.isoformat() if item.deadline else None,
        "is_read": item.is_read,
        "received_at": (item.occurred_at or item.created_at).isoformat(),
        "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
        "created_at": item.created_at.isoformat(),
    }


def find_placement(title, company, kind="job"):
    normalized_title = normalize_match_text(title)
    normalized_company = normalize_match_text(company)
    candidates = Opportunity.query.filter_by(kind=kind).all()

    for candidate in candidates:
        candidate_title = normalize_match_text(candidate.title)
        candidate_company = normalize_match_text(candidate.organization)
        same_company = normalized_company and normalized_company == candidate_company
        same_title = normalized_title == candidate_title
        title_contains = len(normalized_title) >= 8 and (
            normalized_title in candidate_title or candidate_title in normalized_title
        )
        if same_title or (same_company and title_contains):
            return candidate

    return None


def detect_status(text):
    lowered = text.lower()
    for status, keywords in STATUS_RULES:
        if any(keyword in lowered for keyword in keywords):
            return status
    return "Tracked"


def normalize_status(value):
    clean_value = clean_text(value, 60)
    for status, keywords in STATUS_RULES:
        if clean_value.lower() == status.lower() or clean_value.lower() in keywords:
            return status
    return clean_value or "Tracked"


def choose_status(current, incoming):
    rank = {
        "Tracked": 0,
        "Opening": 1,
        "Applied": 2,
        "OA Received": 2,
        "Shortlisted": 3,
        "Interview Scheduled": 4,
        "Deadline": 4,
        "Rejected": 5,
        "Offer": 6,
    }
    return incoming if rank.get(incoming, 0) >= rank.get(current, 0) else current


def detect_event_type(text):
    lowered = text.lower()
    for event_type, keywords in EVENT_RULES:
        if any(keyword in lowered for keyword in keywords):
            return event_type
    return "update"


def detect_deadline(text):
    iso_match = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if iso_match:
        return parse_optional_datetime("-".join(iso_match.groups()))
    india_match = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b", text)
    if india_match:
        day, month, year = india_match.groups()
        return parse_optional_datetime(f"{year}-{int(month):02d}-{int(day):02d}")
    return None


def detect_company(source, title, body):
    sender_match = re.search(r"@([a-z0-9-]+)\.", str(source or "").lower())
    if sender_match:
        return sender_match.group(1).replace("-", " ").title()
    from_match = re.search(r"\bfrom\s+([A-Z][A-Za-z0-9 &.-]{2,40})", f"{title} {body}")
    if from_match:
        return from_match.group(1).strip()
    return ""


def build_action_needed(status, deadline):
    if status in {"OA Received", "Deadline"}:
        suffix = f" before {deadline.strftime('%d %b %Y')}" if deadline else ""
        return f"Open the assessment link and complete the required step{suffix}."
    if status == "Interview Scheduled":
        return "Confirm the interview slot, save the meeting link, and prepare notes."
    if status == "Shortlisted":
        return "Check the next round instructions and add the deadline to reminders."
    if status == "Applied":
        return "Keep this company in watch mode and wait for assessment or recruiter updates."
    if status == "Opening":
        return "Decide whether to apply, then save the role as applied once confirmation arrives."
    if status == "Rejected":
        return "Mark this application closed and save any feedback for later."
    if status == "Offer":
        return "Review the offer details and save the deadline for acceptance."
    return "Review this placement update and decide the next step."


def build_external_id(source, title, body):
    raw = "\n".join((str(source or ""), title, body[:1000]))
    return f"placement:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def normalize_match_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def is_neopat_signal(*values):
    text = normalize_match_text(" ".join(str(value or "") for value in values))
    return "neopat" in text or "neo pat" in text


def detect_applied_at(opportunity, updates):
    if opportunity.kind == "neopat" or is_neopat_signal(opportunity.title, opportunity.organization, opportunity.source, opportunity.notes):
        return None
    applied_updates = [
        item.occurred_at or item.created_at
        for item in updates
        if item.event_type == "application" or "applied" in normalize_match_text(item.title)
    ]
    if applied_updates:
        return min(applied_updates)
    return None


def build_metrics(opportunity, updates, applied_at):
    now = datetime.utcnow()
    deadline = opportunity.deadline
    has_applied = bool(applied_at) or opportunity.status not in {"Opening", "Tracked"}
    return {
        "total_updates": len(updates),
        "unread_updates": sum(1 for item in updates if not item.is_read),
        "has_applied": has_applied,
        "days_since_applied": (now - applied_at).days if applied_at else None,
        "days_to_deadline": (deadline - now).days if deadline else None,
    }
