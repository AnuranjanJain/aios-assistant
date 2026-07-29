import html
import json
import re
from datetime import date, datetime, time, timedelta
from email.utils import parseaddr

from app.models import EmailTask, InboxItem, Opportunity, Reminder, db
from app.services.application_intelligence import classify_tracked_email
from app.services.email_scope import (
    EMAIL_PORTFOLIO_LIMIT,
    clamp_email_limit,
    latest_emails_combined,
)


def _json(value):
    try:
        return json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []


def _first(values, fallback=""):
    return next((str(value).strip() for value in values or [] if str(value).strip()), fallback)


def _organization(email, insight):
    company = _first(_json(insight.companies_json) if insight else [])
    if company:
        return company[:120]
    _name, address = parseaddr(email.sender or "")
    domain = address.split("@", 1)[-1].split(".", 1)[0] if "@" in address else ""
    return domain.replace("-", " ").title()[:120] or "Email"


def _email_text(email):
    return _clean_text(f"{email.subject or ''} {email.snippet or ''} {email.body_text or ''}")


def _clean_text(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"[\u00ad\u034f\u061c\u115f-\u1160\u17b4-\u17b5\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _summary_lines(email, insight):
    raw = _clean_text((insight.summary if insight else "") or email.snippet or email.body_text or email.subject)
    raw = re.split(r"\b(?:unsubscribe|manage preferences|view in browser)\b", raw, maxsplit=1, flags=re.I)[0]
    sentences = [part.strip(" -") for part in re.split(r"(?<=[.!?])\s+|\s+[|•]\s+", raw) if len(part.strip()) >= 18]
    lines = [sentence[:220] for sentence in sentences[:2]]
    category = (insight.category if insight else "general").replace("_", " ").title()
    if len(lines) < 2:
        lines.append(f"This mail is classified as {category.lower()} and should be reviewed in context.")
    actions = _json(insight.suggested_actions_json) + _json(insight.action_items_json) if insight else []
    action = _first(actions, "Review the message and decide the next action.")
    lines.append(f"Next: {_clean_text(action)[:190]}")
    deadline = _deadline_from_email(email)
    if deadline:
        lines.append(f"Deadline: {deadline.strftime('%a, %d %b %Y at %I:%M %p')}.")
    else:
        priority = (insight.priority if insight else "normal").title()
        lines.append(f"Priority: {priority}. Source: {_organization(email, insight)}.")
    return "\n".join(lines[:4])


def _deadline_from_email(email):
    task_deadline = _first_task_due_at(email)
    if task_deadline:
        return task_deadline
    text = _email_text(email).lower()
    anchor = email.sent_at or datetime.utcnow()
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", text)
    if numeric:
        day, month, year = map(int, numeric.groups())
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day, 17)
        except ValueError:
            pass
    days_left = re.search(r"\b(\d{1,2})\s+days?\s+(?:left|remaining)\b", text)
    if days_left:
        return datetime.combine(anchor.date() + timedelta(days=int(days_left.group(1))), time(18, 0))
    if "24 hours left" in text:
        return anchor + timedelta(days=1)
    weekday_match = re.search(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text)
    deadline_cues = ("submit", "submission", "deadline", "due", "closing", "finish line", "rush", "final week")
    if weekday_match and any(cue in text for cue in deadline_cues):
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        weekday = weekdays.index(weekday_match.group(1))
        days_ahead = (weekday - anchor.weekday()) % 7 or 7
        return datetime.combine(anchor.date() + timedelta(days=days_ahead), time(18, 0))
    if any(cue in text for cue in ("final week", "this week")) and any(cue in text for cue in deadline_cues):
        days_ahead = (6 - anchor.weekday()) % 7 or 7
        return datetime.combine(anchor.date() + timedelta(days=days_ahead), time(18, 0))
    return None


def materialize_email_views(limit=EMAIL_PORTFOLIO_LIMIT):
    limit = clamp_email_limit(limit)
    emails = latest_emails_combined(limit)
    counts = {"inbox": 0, "opportunities": 0, "reminders": 0, "today_reminders": 0}
    for email in emails:
        insight = email.insight
        source_key = f"gmail:{email.account_id}:{email.provider_message_id}"
        inbox = InboxItem.query.filter_by(source_key=source_key).first()
        if inbox is None:
            inbox = InboxItem(source_key=source_key, email_message_id=email.id)
            db.session.add(inbox)
            counts["inbox"] += 1
        inbox.sender = email.sender
        inbox.subject = email.subject or "Untitled email"
        inbox.body = email.body_text or email.snippet
        inbox.category = insight.category if insight else "general"
        inbox.confidence = insight.confidence if insight else 0.35
        inbox.summary = _summary_lines(email, insight)
        inbox.next_action = _first(
            _json(insight.suggested_actions_json) + _json(insight.action_items_json) if insight else [],
            "Review this email" if email.is_unread else "",
        )
        inbox.occurred_at = email.sent_at

        tracked = classify_tracked_email(email)
        if tracked:
            opportunity = Opportunity.query.filter_by(source_key=source_key).first()
            if opportunity is None:
                opportunity = Opportunity(source_key=source_key, email_message_id=email.id)
                db.session.add(opportunity)
                counts["opportunities"] += 1
            opportunity.kind = (
                tracked.get("opportunity_kind", "hackathon")
                if tracked["kind"] == "hackathon"
                else "job"
            )
            opportunity.title = tracked["role"][:180] or email.subject[:180] or "Email opportunity"
            opportunity.organization = tracked["company"][:120]
            opportunity.status = tracked.get("status") or tracked["stage"].replace("_", " ").title()
            opportunity.source = f"Gmail: {email.account.email}" if email.account else "Gmail"
            opportunity.deadline = tracked["deadline"] or _deadline_from_email(email)
            opportunity.notes = _summary_lines(email, insight)[:2000]

    email_ids = [email.id for email in emails]
    today = date.today()
    active_keys = set()
    seen_tasks = set()
    tasks = (
        EmailTask.query.filter_by(status="open")
        .filter(EmailTask.email_id.in_(email_ids))
        .order_by(EmailTask.due_at.asc(), EmailTask.updated_at.desc())
        .all()
        if email_ids
        else []
    )
    for task in tasks:
        if not task.email:
            continue
        insight = task.email.insight
        priority = task.priority or (insight.priority if insight else "normal")
        due_at = task.due_at
        due_this_year = bool(due_at and due_at.date().year == today.year)
        actionable_today = bool(
            due_this_year and due_at.date() <= today
        ) or (due_at is None and priority in {"high", "urgent"})
        task_key = re.sub(r"\W+", " ", task.title.lower()).strip()
        if not actionable_today or task_key in seen_tasks:
            continue
        seen_tasks.add(task_key)
        source_key = f"email-task:{task.id}"
        active_keys.add(source_key)
        reminder = Reminder.query.filter_by(source_key=source_key).first()
        if reminder is None:
            reminder = Reminder(source_key=source_key, title=task.title[:180], due_at=_task_due_at(task, today))
            db.session.add(reminder)
            counts["reminders"] += 1
        reminder.title = task.title[:180]
        reminder.due_at = _task_due_at(task, today)
        reminder.channel = "desktop"
        reminder.notification_type = "email_action"
        reminder.priority = priority or "normal"
        reminder.metadata_json = json.dumps(
            {
                "email_id": task.email_id,
                "subject": task.email.subject,
                "sender": task.email.sender,
                "account_email": task.email.account.email if task.email.account else "",
                "summary": (insight.summary if insight else task.email.snippet or "")[:500],
                "message": f"From Gmail: {task.email.subject}",
            },
            ensure_ascii=True,
        )
        counts["today_reminders"] += 1

    stale_query = Reminder.query.filter(Reminder.source_key.like("email-task:%"))
    if active_keys:
        stale_query = stale_query.filter(Reminder.source_key.notin_(active_keys))
    for reminder in stale_query.all():
        db.session.delete(reminder)

    db.session.commit()
    return {
        "ok": True,
        **counts,
        "processed": len(emails),
        "emails_scanned": len(emails),
        "accounts_scanned": len({email.account_id for email in emails}),
        "combined_limit": limit,
    }


def _first_task_due_at(email):
    due_dates = [task.due_at for task in email.tasks if task.due_at]
    return min(due_dates) if due_dates else None


def _task_due_at(task, today=None):
    if task.due_at:
        return task.due_at
    today = today or date.today()
    return datetime.combine(today, time(18, 0))
