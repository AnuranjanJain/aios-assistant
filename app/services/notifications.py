import json
from datetime import date, datetime, time, timedelta

from app.models import (
    EmailMessage,
    GitHubRepository,
    LearningItem,
    Opportunity,
    PlanningEvent,
    Reminder,
    db,
)
from app.services.settings import get_setting


DONE_STATUSES = {"completed", "done", "cancelled"}
DEFAULT_QUIET_START = "22:00"
DEFAULT_QUIET_END = "07:00"


def send_desktop_notification(title, message):
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name="AiOS Assistant",
            timeout=8,
        )
        return True
    except Exception:
        print(f"[AiOS notification] {title}: {message}")
        return False


def notification_center(now=None, send=False):
    now = parse_datetime(now) or datetime.utcnow()
    generated = generate_notifications(now)
    dispatched = dispatch_due_notifications(now, send=send)
    upcoming = Reminder.query.filter(Reminder.is_done.is_(False)).order_by(Reminder.due_at.asc()).limit(50).all()
    return {
        "ok": True,
        "generated": generated,
        "dispatched": dispatched,
        "quiet_hours": quiet_hours_status(now),
        "notifications": [serialize_notification(item) for item in upcoming],
    }


def generate_notifications(now=None):
    now = parse_datetime(now) or datetime.utcnow()
    created = []
    created.extend(deadline_notifications(now))
    created.extend(meeting_notifications(now))
    created.extend(unanswered_email_notifications(now))
    created.extend(learning_notifications(now))
    created.extend(github_inactivity_notifications(now))
    created.extend(hackathon_notifications(now))
    created.extend(daily_review_notifications(now))
    created.extend(morning_planning_notifications(now))
    created.extend(calendar_change_notifications(now))
    db.session.commit()
    return [serialize_notification(item) for item in created]


def deadline_notifications(now):
    rows = PlanningEvent.query.filter(
        PlanningEvent.deadline.isnot(None),
        PlanningEvent.status.notin_(list(DONE_STATUSES)),
        PlanningEvent.deadline <= now + timedelta(days=2),
    ).limit(80).all()
    return [
        upsert_notification(
            f"planning-deadline:{item.id}:{item.deadline.date().isoformat()}",
            f"Deadline: {item.title}",
            item.work_left or item.next_question or "Finish this before the deadline.",
            due_before(item.deadline, smart_lead_minutes("deadline", item.priority, item.deadline, now)),
            "deadline",
            smart_priority("deadline", item.priority, item.deadline, now),
            {"planning_event_id": item.id, "deadline": item.deadline.isoformat()},
        )
        for item in rows
    ]


def meeting_notifications(now):
    rows = PlanningEvent.query.filter(
        PlanningEvent.event_type == "meeting",
        PlanningEvent.status.notin_(list(DONE_STATUSES)),
        PlanningEvent.planned_start.isnot(None),
        PlanningEvent.planned_start <= now + timedelta(days=1),
    ).limit(50).all()
    return [
        upsert_notification(
            f"meeting:{item.id}:{item.planned_start.isoformat()}",
            f"Meeting soon: {item.title}",
            item.work_left or "Prepare notes, links, and questions.",
            due_before(item.planned_start, 15),
            "meeting",
            smart_priority("meeting", item.priority, item.planned_start, now),
            {"planning_event_id": item.id, "planned_start": item.planned_start.isoformat()},
        )
        for item in rows
    ]


def unanswered_email_notifications(now):
    stale_cutoff = now - timedelta(days=3)
    rows = EmailMessage.query.filter(
        EmailMessage.is_unread.is_(True),
        EmailMessage.sent_at.isnot(None),
        EmailMessage.sent_at <= stale_cutoff,
    ).order_by(EmailMessage.sent_at.asc()).limit(25).all()
    return [
        upsert_notification(
            f"unanswered-email:{item.id}",
            f"Unanswered email: {item.subject or 'Email'}",
            f"From {item.sender or 'unknown sender'}; unread for 3+ days.",
            now,
            "unanswered_email",
            "high",
            {"email_id": item.id, "sent_at": item.sent_at.isoformat() if item.sent_at else None},
        )
        for item in rows
    ]


def learning_notifications(now):
    rows = LearningItem.query.filter(
        LearningItem.status.notin_(list(DONE_STATUSES)),
    ).limit(80).all()
    due = []
    for item in rows:
        target = item.next_revision_at or item.scheduled_at or item.deadline
        if target and target <= now + timedelta(days=1):
            due.append(
                upsert_notification(
                    f"learning:{item.id}:{target.date().isoformat()}",
                    f"Learning: {item.title}",
                    "Review, revise, or log progress before this goes stale.",
                    target,
                    "learning",
                    smart_priority("learning", "high" if item.deadline and item.deadline <= now + timedelta(days=1) else "normal", target, now),
                    {"learning_item_id": item.id, "target_at": target.isoformat()},
                )
            )
    return due


def github_inactivity_notifications(now):
    rows = GitHubRepository.query.filter(GitHubRepository.inactive.is_(True)).limit(50).all()
    due = []
    for item in rows:
        due.append(
            upsert_notification(
                f"github-inactivity:{item.id}:{now.date().isoformat()}",
                f"GitHub inactivity: {item.repo_full_name}",
                item.suggested_next_task or "Pick one small issue, commit, or archive the project.",
                now,
                "github_inactivity",
                "normal",
                {"repository_id": item.id, "repo": item.repo_full_name},
            )
        )
    return due


def hackathon_notifications(now):
    rows = Opportunity.query.filter(
        Opportunity.kind == "hackathon",
        Opportunity.deadline.isnot(None),
        Opportunity.deadline <= now + timedelta(days=7),
    ).limit(50).all()
    return [
        upsert_notification(
            f"hackathon:{item.id}:{item.deadline.date().isoformat()}",
            f"Hackathon: {item.title}",
            "Check submission plan, team status, and build progress.",
            due_before(item.deadline, 24 * 60),
            "hackathon",
            smart_priority("hackathon", "high", item.deadline, now),
            {"opportunity_id": item.id, "deadline": item.deadline.isoformat()},
            opportunity=item,
        )
        for item in rows
    ]


def daily_review_notifications(now):
    due_at = datetime.combine(now.date(), time(18, 0))
    return [
        upsert_notification(
            f"daily-review:{now.date().isoformat()}",
            "Daily Review",
            "Log what you completed, blockers, hours worked, and deadline changes.",
            due_at,
            "daily_review",
            "normal",
            {"date": now.date().isoformat()},
        )
    ]


def morning_planning_notifications(now):
    due_at = datetime.combine(now.date(), time(7, 0))
    return [
        upsert_notification(
            f"morning-planning:{now.date().isoformat()}",
            "Morning Planning",
            "Review today's schedule, risks, and highest-priority first block.",
            due_at,
            "morning_planning",
            "normal",
            {"date": now.date().isoformat()},
        )
    ]


def calendar_change_notifications(now):
    rows = PlanningEvent.query.filter(
        PlanningEvent.source == "calendar",
        PlanningEvent.updated_at >= now - timedelta(days=1),
        PlanningEvent.planned_start >= now,
    ).limit(25).all()
    return [
        upsert_notification(
            f"calendar-change:{item.id}:{item.updated_at.isoformat()}",
            f"Calendar changed: {item.title}",
            "Review whether your plan needs to move around this event.",
            now,
            "calendar_change",
            "normal",
            {"planning_event_id": item.id, "updated_at": item.updated_at.isoformat()},
        )
        for item in rows
    ]


def upsert_notification(source_key, title, message, due_at, notification_type, priority, metadata=None, opportunity=None):
    due_at = apply_quiet_hours(parse_datetime(due_at) or datetime.utcnow())
    row = Reminder.query.filter_by(source_key=source_key).first()
    if row is None:
        row = Reminder(source_key=source_key, title=title[:180], due_at=due_at, channel="desktop", opportunity=opportunity)
        db.session.add(row)
    row.title = title[:180]
    row.due_at = due_at
    row.notification_type = notification_type
    row.priority = priority
    row.metadata_json = dump_metadata(message, metadata)
    if row.is_done:
        row.is_done = False
    return row


def dispatch_due_notifications(now=None, send=False):
    now = parse_datetime(now) or datetime.utcnow()
    if quiet_hours_status(now)["active"]:
        return {"sent": 0, "deferred": True, "items": []}
    due = (
        Reminder.query.filter(Reminder.is_done.is_(False))
        .filter(Reminder.is_read.is_(False))
        .filter(Reminder.due_at <= now)
        .order_by(Reminder.due_at.asc())
        .limit(10)
        .all()
    )
    due.sort(key=lambda item: (priority_rank(item.priority), item.due_at))
    sent = []
    for item in due:
        metadata = load_metadata(item)
        ok = send_desktop_notification(item.title, metadata.get("message") or item.channel) if send else True
        if ok:
            item.notified_at = now
            item.is_read = True
            item.snoozed_until = None
            sent.append(serialize_notification(item))
    db.session.commit()
    return {"sent": len(sent), "deferred": False, "items": sent}


def snooze_notification(reminder_id, minutes=30, now=None):
    now = parse_datetime(now) or datetime.utcnow()
    reminder = db.session.get(Reminder, int(reminder_id))
    if reminder is None:
        return {"ok": False, "error": "Notification not found."}
    minutes = max(5, min(7 * 24 * 60, int(minutes or 30)))
    reminder.due_at = apply_quiet_hours(now + timedelta(minutes=minutes))
    reminder.snoozed_until = reminder.due_at
    reminder.is_read = False
    reminder.is_done = False
    db.session.commit()
    return {"ok": True, "notification": serialize_notification(reminder)}


def reschedule_notification(reminder_id, due_at):
    reminder = db.session.get(Reminder, int(reminder_id))
    if reminder is None:
        return {"ok": False, "error": "Notification not found."}
    parsed = parse_datetime(due_at)
    if parsed is None:
        return {"ok": False, "error": "Valid due_at is required."}
    metadata = load_metadata(reminder)
    metadata["rescheduled_from"] = reminder.due_at.isoformat()
    reminder.due_at = apply_quiet_hours(parsed)
    reminder.snoozed_until = None
    reminder.is_read = False
    reminder.is_done = False
    reminder.metadata_json = json.dumps(metadata, ensure_ascii=False)
    db.session.commit()
    return {"ok": True, "notification": serialize_notification(reminder)}


def smart_priority(notification_type, base_priority, target_at=None, now=None):
    now = parse_datetime(now) or datetime.utcnow()
    target_at = parse_datetime(target_at)
    base = str(base_priority or "normal").lower()
    if notification_type in {"unanswered_email", "hackathon"}:
        base = "high"
    if target_at:
        hours = (target_at - now).total_seconds() / 3600
        if hours <= 2:
            return "urgent"
        if hours <= 24 and base in {"normal", "medium"}:
            return "high"
    return base if base in {"urgent", "high", "normal", "low"} else "normal"


def smart_lead_minutes(notification_type, priority, target_at, now):
    priority = smart_priority(notification_type, priority, target_at, now)
    if priority == "urgent":
        return 60
    if priority == "high":
        return 180
    return 24 * 60


def priority_rank(priority):
    return {"urgent": 0, "high": 1, "normal": 2, "low": 3}.get(str(priority or "normal").lower(), 2)


def due_before(target_at, minutes):
    target_at = parse_datetime(target_at) or datetime.utcnow()
    return target_at - timedelta(minutes=minutes)


def quiet_hours_status(now=None):
    now = parse_datetime(now) or datetime.utcnow()
    start = parse_time(get_setting("NOTIFICATION_QUIET_START", DEFAULT_QUIET_START)) or time(22, 0)
    end = parse_time(get_setting("NOTIFICATION_QUIET_END", DEFAULT_QUIET_END)) or time(7, 0)
    active = time_in_quiet_hours(now.time(), start, end)
    return {
        "active": active,
        "start": start.isoformat(timespec="minutes"),
        "end": end.isoformat(timespec="minutes"),
        "next_allowed_at": next_quiet_end(now, start, end).isoformat() if active else now.isoformat(),
    }


def apply_quiet_hours(due_at):
    status = quiet_hours_status(due_at)
    if status["active"]:
        return parse_datetime(status["next_allowed_at"]) or due_at
    return due_at


def time_in_quiet_hours(value, start, end):
    if start == end:
        return False
    if start < end:
        return start <= value < end
    return value >= start or value < end


def next_quiet_end(now, start, end):
    candidate = datetime.combine(now.date(), end)
    if start > end and now.time() >= start:
        candidate += timedelta(days=1)
    if start < end and now.time() >= end:
        candidate += timedelta(days=1)
    return candidate


def dump_metadata(message, metadata):
    payload = dict(metadata or {})
    payload["message"] = message
    return json.dumps(payload, ensure_ascii=False)


def load_metadata(reminder):
    try:
        parsed = json.loads(reminder.metadata_json or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def serialize_notification(item):
    return {
        "id": item.id,
        "title": item.title,
        "message": load_metadata(item).get("message", ""),
        "type": item.notification_type or "reminder",
        "priority": item.priority or "normal",
        "due_at": item.due_at.isoformat(),
        "channel": item.channel,
        "source_key": item.source_key,
        "is_done": item.is_done,
        "is_read": item.is_read,
        "notified_at": item.notified_at.isoformat() if item.notified_at else None,
        "snoozed_until": item.snoozed_until.isoformat() if item.snoozed_until else None,
        "metadata": load_metadata(item),
    }


def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(raw[:10]), time(9))
        except ValueError:
            return None


def parse_time(value):
    try:
        return time.fromisoformat(str(value or ""))
    except ValueError:
        return None
