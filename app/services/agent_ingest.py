import json
from datetime import datetime

from app.models import AgentDecision, InboxItem, db
from app.services.hackathons import ingest_hackathon_signal
from app.services.placements import ingest_placement_signal
from app.services.reminder_engine import create_follow_up_reminder


TRACKED_CATEGORIES = {"job", "hackathon", "interview", "deadline", "meeting"}


def ingest_message(sender, subject, body, source, classifier, provider, model=None):
    result = classifier.classify(subject, body)

    inbox_item = InboxItem(
        sender=sender,
        subject=subject,
        body=body,
        category=result.category,
        confidence=result.confidence,
    )
    db.session.add(inbox_item)

    opportunity = None
    if result.category == "hackathon":
        opportunity, _update, _created = ingest_hackathon_signal(
            title=result.title or subject,
            source=source,
            body=body,
            organization=result.organization or sender,
            status=result.status,
            deadline=result.deadline,
        )
    elif result.category in TRACKED_CATEGORIES:
        opportunity, _update, created = ingest_placement_signal(
            title=result.title or subject,
            source=source,
            body=body,
            organization=result.organization or sender,
            status=result.status,
            deadline=parse_optional_datetime(result.deadline),
        )
        if created and not opportunity.reminders:
            db.session.add(create_follow_up_reminder(opportunity))

    decision = AgentDecision(
        input_type="message",
        provider=provider,
        model=model,
        decision_json=json.dumps(result.__dict__, ensure_ascii=True),
        confidence=result.confidence,
    )
    db.session.add(decision)

    return {
        "inbox_item": inbox_item,
        "opportunity": opportunity,
        "classification": result,
        "decision": decision,
    }


def parse_optional_datetime(value):
    if not value:
        return None

    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None
