from datetime import datetime, timedelta

from app.models import Reminder


def create_follow_up_reminder(opportunity):
    return Reminder(
        title=f"Follow up: {opportunity.title}",
        due_at=datetime.utcnow() + timedelta(days=7),
        channel="dashboard",
        opportunity=opportunity,
    )


def create_deadline_reminder(opportunity):
    if not opportunity.deadline:
        return None

    return Reminder(
        title=f"Deadline soon: {opportunity.title}",
        due_at=opportunity.deadline - timedelta(days=1),
        channel="dashboard",
        opportunity=opportunity,
    )
