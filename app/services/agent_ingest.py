import json
from datetime import datetime

from app.models import AgentDecision, InboxItem, Opportunity, db
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
    if result.category in TRACKED_CATEGORIES:
        opportunity = Opportunity(
            kind="job" if result.category == "interview" else result.category,
            title=(result.title or subject)[:180],
            organization=result.organization or sender or "Unknown",
            status=result.status,
            source=source,
            deadline=parse_optional_datetime(result.deadline),
            notes=result.action_needed or result.reason,
        )
        db.session.add(opportunity)
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
