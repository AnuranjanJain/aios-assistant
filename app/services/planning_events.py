import json
import re
import urllib.error
import urllib.request
from datetime import date, datetime, time, timedelta

from flask import current_app

from app.models import EmailTask, Opportunity, PlanTask, PlanningEvent, db
from app.services.planning_engine import PlanningEngine
from app.services.settings import get_effective_config

USER_EDITABLE_FIELDS = {"status", "work_done", "work_left", "planned_start", "planned_minutes"}
WORK_BLOCK_HOURS = [9, 11, 14, 16, 19]


def _dump(value):
    return json.dumps(value or {}, ensure_ascii=False)


def _json(value):
    try:
        return json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}


def _clean(value, limit):
    return str(value or "").strip()[:limit]


def _first_url(text):
    match = re.search(r"https?://[^\s)>\"]+", text or "")
    return match.group(0)[:500] if match else ""


def _planned_slot(offset, target_date=None):
    block_date = target_date or (date.today() + timedelta(days=offset // len(WORK_BLOCK_HOURS)))
    hour = WORK_BLOCK_HOURS[offset % len(WORK_BLOCK_HOURS)]
    return datetime.combine(block_date, time(hour=hour))


def _deadline_work_slot(event_type, deadline, offset):
    if not deadline:
        return _planned_slot(offset)
    if event_type == "email":
        candidate = deadline - timedelta(hours=2)
        if candidate.date() >= date.today():
            return candidate
        return _planned_slot(offset)

    days_before = {"hackathon": 2, "goal": 1, "repo": 1}.get(event_type, 0)
    target_date = max(date.today(), (deadline - timedelta(days=days_before)).date())
    candidate = _planned_slot(offset, target_date)
    if candidate >= deadline:
        candidate = deadline - timedelta(hours=2)
    if candidate.date() < date.today():
        return _planned_slot(offset)
    return candidate


def upsert_event(source_key, **data):
    event = PlanningEvent.query.filter_by(source_key=source_key).first()
    is_new = event is None
    if event is None:
        event = PlanningEvent(source_key=source_key)
        db.session.add(event)

    for key, value in data.items():
        if not is_new and key in USER_EDITABLE_FIELDS and getattr(event, key, None):
            continue
        if not is_new and key == "metadata_json":
            existing = _json(event.metadata_json)
            incoming = _json(value)
            incoming.update(existing)
            event.metadata_json = _dump(incoming)
            continue
        if hasattr(event, key) and value not in (None, ""):
            setattr(event, key, value)
    return event


def generate_events_from_sources():
    created_or_updated = 0
    offset = 0

    hackathons = Opportunity.query.filter_by(kind="hackathon").order_by(Opportunity.updated_at.desc()).limit(40).all()
    for item in hackathons:
        repo_url = _first_url(f"{item.source or ''} {item.notes or ''}")
        event = upsert_event(
            f"hackathon:{item.id}",
            event_type="hackathon",
            source="hackathon",
            title=item.title,
            project=item.organization or item.title,
            idea=item.notes or "",
            deadline=item.deadline,
            planned_start=_deadline_work_slot("hackathon", item.deadline, offset),
            planned_minutes=90,
            priority="high" if item.deadline and item.deadline.date() <= date.today() + timedelta(days=7) else "normal",
            status="planned" if item.status.lower() in {"tracked", "opening"} else item.status.lower().replace(" ", "_"),
            work_done=f"Current status: {item.status}",
            work_left=item.notes or "Define prototype, repo work, submission assets, and final review.",
            repo_url=repo_url,
            next_question=f"What did you finish for {item.title}, and what is left before the deadline?",
            metadata_json=_dump({"opportunity_id": item.id, "kind": item.kind}),
        )
        refresh_repo_activity(event)
        created_or_updated += 1
        offset += 1

    email_tasks = EmailTask.query.filter_by(status="open").order_by(EmailTask.created_at.desc()).limit(50).all()
    for task in email_tasks:
        email = task.email
        event = upsert_event(
            f"email_task:{task.id}",
            event_type="email",
            source="gmail",
            title=task.title,
            project=email.subject if email else "Email task",
            idea=email.snippet if email else "",
            deadline=task.due_at,
            planned_start=_deadline_work_slot("email", task.due_at, offset),
            planned_minutes=45,
            priority=task.priority,
            status=task.status,
            work_done="Created from email signal.",
            work_left=task.title,
            next_question=f"Did you complete this email task: {task.title}?",
            metadata_json=_dump({"email_id": email.id if email else None, "task_id": task.id}),
        )
        created_or_updated += 1
        offset += 1

    plan_tasks = PlanTask.query.filter(PlanTask.status != "completed").order_by(PlanTask.updated_at.desc()).limit(50).all()
    for task in plan_tasks:
        event = upsert_event(
            f"goal_task:{task.id}",
            event_type="goal",
            source="goal_planner",
            title=task.title,
            project=task.plan.title if task.plan else "Goal",
            idea=task.description or task.ai_summary or "",
            planned_start=_planned_slot(offset),
            planned_minutes=task.estimated_minutes,
            priority="normal",
            status=task.status,
            work_done=task.ai_summary or "",
            work_left=task.suggested_next or task.description or "Log what you completed and the next resource.",
            next_question=f"How is '{task.title}' going? Which video/resource did you complete?",
            metadata_json=_dump({"plan_task_id": task.id, "plan_id": task.plan_id}),
        )
        created_or_updated += 1
        offset += 1

    db.session.commit()
    return {"ok": True, "events": created_or_updated}


def create_manual_event(data):
    event_type = _clean(data.get("event_type", "manual"), 60) or "manual"
    title = _clean(data.get("title"), 240)
    if not title:
        return {"ok": False, "message": "Title is required."}
    project = _clean(data.get("project"), 180)
    repo_url = _clean(data.get("repo_url"), 500)
    event = upsert_event(
        f"manual:{datetime.utcnow().timestamp()}",
        event_type=event_type,
        source="manual",
        title=title,
        project=project,
        idea=_clean(data.get("idea"), 2000),
        deadline=parse_datetime(data.get("deadline")),
        planned_start=parse_datetime(data.get("planned_start")),
        planned_minutes=int(data.get("planned_minutes") or 45),
        priority=_clean(data.get("priority", "normal"), 40),
        status=_clean(data.get("status", "planned"), 40),
        work_done=_clean(data.get("work_done"), 2000),
        work_left=_clean(data.get("work_left"), 2000),
        repo_url=repo_url,
        next_question=_clean(data.get("next_question"), 260)
        or default_next_question(event_type, title, project, repo_url),
        metadata_json=_dump({"manual": True}),
    )
    refresh_repo_activity(event)
    db.session.commit()
    return {"ok": True, "event": serialize_event(event)}


def default_next_question(event_type, title, project="", repo_url=""):
    subject = project or title
    if event_type == "learning_video":
        return f"Which video did you complete for {subject}, and what notes should I remember?"
    if event_type == "hackathon":
        return f"What changed in {title}? Update work done, work left, repo progress, and submission blockers."
    if event_type == "repo" or repo_url:
        return f"What work did you do in the repo for {subject}?"
    return f"What progress did you make on {title}, and what should be rescheduled?"


def update_event_progress(event_id, data):
    event = db.session.get(PlanningEvent, int(event_id))
    if event is None:
        return {"ok": False, "message": "Planning event not found."}

    if "work_done" in data:
        event.work_done = _clean(data.get("work_done"), 2000)
    if "work_left" in data:
        event.work_left = _clean(data.get("work_left"), 2000)
    if "status" in data:
        event.status = _clean(data.get("status"), 40) or event.status
    if "planned_start" in data:
        event.planned_start = parse_datetime(data.get("planned_start")) or event.planned_start
    if "planned_minutes" in data:
        event.planned_minutes = parse_minutes(data.get("planned_minutes"), event.planned_minutes)
    progress_note = _clean(data.get("progress_note") or data.get("answer"), 2000)
    if progress_note:
        metadata = _json(event.metadata_json)
        progress_log = metadata.get("progress_log") or []
        progress_log.append(
            {
                "at": datetime.utcnow().isoformat(),
                "note": progress_note,
                "question": event.next_question or build_next_question(event),
            }
        )
        metadata["progress_log"] = progress_log[-20:]
        event.metadata_json = _dump(metadata)
        if not event.work_done:
            event.work_done = progress_note
    event.last_prompted_at = datetime.utcnow()
    event.next_question = build_next_question(event)
    refresh_repo_activity(event)
    db.session.commit()
    return {"ok": True, "event": serialize_event(event)}


def build_next_question(event):
    return default_next_question(event.event_type, event.title, event.project or "", event.repo_url or "")


def planning_board():
    generate_events_from_sources()
    events = PlanningEvent.query.order_by(
        PlanningEvent.status.asc(),
        PlanningEvent.deadline.is_(None),
        PlanningEvent.deadline.asc(),
        PlanningEvent.planned_start.asc(),
    ).limit(120).all()
    blocks = plan_blocks(events)
    questions = question_queue(events)
    return {
        "events": [serialize_event(event) for event in events],
        "counts": {
            "total": len(events),
            "hackathons": sum(1 for event in events if event.event_type == "hackathon"),
            "emails": sum(1 for event in events if event.event_type == "email"),
            "goals": sum(1 for event in events if event.event_type == "goal"),
            "today": sum(1 for event in events if event_is_in_window(event, days=1)),
            "tomorrow": sum(1 for event in events if event_is_on_date(event, date.today() + timedelta(days=1))),
            "week": sum(1 for event in events if event_is_in_window(event, days=7)),
            "next_week": sum(1 for event in events if event_is_in_date_range(event, 7, 13)),
            "month": sum(1 for event in events if event_is_in_window(event, days=31)),
            "open": sum(1 for event in events if event.status not in {"completed", "done"}),
        },
        "agenda": agenda_outline(events),
        "plan_blocks": blocks,
        "question_queue": questions,
        "briefing": planner_briefing(events, blocks, questions),
        "monthly": monthly_outline(events),
    }


def event_is_in_window(event, days):
    anchor = event.deadline or event.planned_start
    if not anchor:
        return False
    today = date.today()
    return today <= anchor.date() <= today + timedelta(days=days - 1)


def event_is_on_date(event, target_date):
    anchor = event.deadline or event.planned_start
    return bool(anchor and anchor.date() == target_date)


def event_is_in_date_range(event, start_days, end_days):
    anchor = event.deadline or event.planned_start
    if not anchor:
        return False
    today = date.today()
    return today + timedelta(days=start_days) <= anchor.date() <= today + timedelta(days=end_days)


def monthly_outline(events):
    weeks = {}
    for event in events:
        anchor = (event.deadline or event.planned_start or datetime.utcnow()).date()
        week_start = anchor - timedelta(days=anchor.weekday())
        weeks.setdefault(week_start.isoformat(), []).append(event.title)
    return [{"week_start": key, "focus": values[:5]} for key, values in sorted(weeks.items())[:6]]


def agenda_outline(events):
    active = [event for event in events if event.status not in {"completed", "done"}]
    return {
        "today": [serialize_event(event) for event in active if event_is_in_window(event, days=1)][:8],
        "tomorrow": [serialize_event(event) for event in active if event_is_on_date(event, date.today() + timedelta(days=1))][:8],
        "week": [serialize_event(event) for event in active if event_is_in_window(event, days=7)][:12],
        "next_week": [serialize_event(event) for event in active if event_is_in_date_range(event, 7, 13)][:12],
        "month": [serialize_event(event) for event in active if event_is_in_window(event, days=31)][:20],
    }


def plan_blocks(events):
    return PlanningEngine(events, lambda event: _json(event.metadata_json)).build()


def serialize_plan_block(event):
    start = event.planned_start or event.deadline or datetime.utcnow()
    return {
        "event_id": event.id,
        "title": event.title,
        "project": event.project or "",
        "event_type": event.event_type,
        "start": start.isoformat(),
        "duration_minutes": event.planned_minutes,
        "deadline": event.deadline.isoformat() if event.deadline else None,
        "next_action": event.work_left or event.next_question or build_next_question(event),
        "status": event.status,
    }


def planner_briefing(events, blocks, questions):
    active = [event for event in events if event.status not in {"completed", "done"}]
    blocked = [event for event in active if event.status == "blocked"]
    due_week = [event for event in active if event_is_in_window(event, days=7)]
    today_count = len(blocks["today"])
    week_count = len(blocks["week"])
    month_count = len(blocks["month"])
    if today_count:
        headline = f"{today_count} planned block{'s' if today_count != 1 else ''} today."
    elif week_count:
        headline = f"{week_count} active block{'s' if week_count != 1 else ''} this week."
    elif active:
        headline = f"{len(active)} open planning row{'s' if len(active) != 1 else ''}."
    else:
        headline = "No open planning rows."
    return {
        "headline": headline,
        "today_count": today_count,
        "week_count": week_count,
        "month_count": month_count,
        "needs_answer_count": len(questions),
        "blocked_count": len(blocked),
        "focus": [block["title"] for block in blocks["today"][:3]]
        or [block["title"] for block in blocks["week"][:3]],
        "due_soon": [event.title for event in due_week[:5]],
        "ask_next": [item["question"] for item in questions[:3]],
    }


def question_queue(events):
    active = [
        event
        for event in events
        if event.status not in {"completed", "done", "paused"}
        and (event.next_question or build_next_question(event))
    ]
    active.sort(key=question_priority)
    return [serialize_question(event) for event in active[:10]]


def question_priority(event):
    status_rank = {"blocked": 0, "in_progress": 1, "open": 2, "planned": 3}
    anchor = event.deadline or event.planned_start or datetime.utcnow() + timedelta(days=365)
    last_prompted = event.last_prompted_at or datetime(1970, 1, 1)
    return (status_rank.get(event.status, 4), anchor, last_prompted)


def serialize_question(event):
    metadata = _json(event.metadata_json)
    return {
        "event_id": event.id,
        "question": event.next_question or build_next_question(event),
        "title": event.title,
        "project": event.project or "",
        "event_type": event.event_type,
        "status": event.status,
        "deadline": event.deadline.isoformat() if event.deadline else None,
        "last_prompted_at": event.last_prompted_at.isoformat() if event.last_prompted_at else None,
        "last_progress_note": latest_progress_note(metadata),
    }


def serialize_event(event):
    metadata = _json(event.metadata_json)
    return {
        "id": event.id,
        "event_type": event.event_type,
        "source": event.source,
        "title": event.title,
        "project": event.project or "",
        "idea": event.idea or "",
        "deadline": event.deadline.isoformat() if event.deadline else None,
        "planned_start": event.planned_start.isoformat() if event.planned_start else None,
        "planned_minutes": event.planned_minutes,
        "priority": event.priority,
        "status": event.status,
        "work_done": event.work_done or "",
        "work_left": event.work_left or "",
        "repo_url": event.repo_url or "",
        "repo_latest_activity": event.repo_latest_activity or "",
        "next_question": event.next_question or build_next_question(event),
        "last_progress_note": latest_progress_note(metadata),
        "metadata": metadata,
        "updated_at": event.updated_at.isoformat(),
    }


def latest_progress_note(metadata):
    progress_log = metadata.get("progress_log") or []
    if not progress_log:
        return ""
    latest = progress_log[-1]
    if isinstance(latest, dict):
        return str(latest.get("note") or "")
    return ""


def parse_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(raw), time(hour=9))
        except ValueError:
            return None


def parse_minutes(value, fallback=45):
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(5, min(480, minutes))


def refresh_repo_activity(event):
    if not event.repo_url or "github.com" not in event.repo_url.lower():
        return
    repo = parse_github_repo(event.repo_url)
    if not repo:
        return
    try:
        headers = github_headers()
        commits = github_json(f"https://api.github.com/repos/{repo}/commits?per_page=3", headers)
        open_issues = github_json(
            f"https://api.github.com/search/issues?q=repo:{repo}+type:issue+state:open&per_page=1",
            headers,
        )
        open_prs = github_json(
            f"https://api.github.com/search/issues?q=repo:{repo}+type:pr+state:open&per_page=1",
            headers,
        )
        summary = summarize_repo_activity(commits, open_issues, open_prs)
        if summary:
            event.repo_latest_activity = summary
        if commits:
            commit = commits[0]["commit"]
            message = commit["message"].splitlines()[0]
            if not event.work_done:
                event.work_done = f"Latest repo work: {message}"
    except (OSError, urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError):
        if not event.repo_latest_activity:
            event.repo_latest_activity = "Repo linked; latest activity not fetched yet."


def github_headers():
    headers = {"User-Agent": "aios-local-planner"}
    try:
        token = get_effective_config(current_app.config).get("GITHUB_TOKEN", "").strip()
    except RuntimeError:
        token = ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_json(url, headers):
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=2.5) as response:
        return json.loads(response.read().decode("utf-8"))


def summarize_repo_activity(commits, open_issues, open_prs):
    parts = []
    if commits:
        commit_parts = []
        for item in commits[:3]:
            commit = item["commit"]
            message = commit["message"].splitlines()[0]
            when = commit["committer"]["date"][:10]
            commit_parts.append(f"{when} {message}")
        parts.append("Recent commits: " + " | ".join(commit_parts))
    issue_count = int((open_issues or {}).get("total_count") or 0)
    pr_count = int((open_prs or {}).get("total_count") or 0)
    if issue_count or pr_count:
        parts.append(f"Open GitHub work: {issue_count} issues, {pr_count} PRs")
    return ". ".join(parts)[:2000]


def parse_github_repo(url):
    match = re.search(r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s.#?]+)", url, re.I)
    if not match:
        return ""
    return f"{match.group('owner')}/{match.group('repo').replace('.git', '')}"
