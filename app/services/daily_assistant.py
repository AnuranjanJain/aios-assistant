import json
from datetime import date, datetime, time, timedelta

from app.models import DailyAssistantEntry, PlanningEvent, db
from app.services.planning_events import planning_board, update_event_progress
from app.services.planning_engine import PlanningEngine


EVENING_QUESTIONS = [
    "What did you complete?",
    "What blocked you?",
    "Hours worked?",
    "Need to move deadlines?",
    "Need to modify priorities?",
]

MORNING_BRIEFING_AT = time(6, 0)
EVENING_CHECKIN_AT = time(18, 0)


def _dump(value):
    return json.dumps(value or [], ensure_ascii=False)


def _dump_object(value):
    return json.dumps(value or {}, ensure_ascii=False)


def _json(value, fallback=None):
    if fallback is None:
        fallback = []
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def generate_morning_briefing(target_date=None):
    target_date = parse_date(target_date) or date.today()
    board = planning_board()
    blocks = plan_blocks_for_date(target_date)
    schedule = [normalize_schedule_item(item) for item in blocks]
    explanations = [explain_selection(item) for item in schedule]
    risks = identify_risks(board, schedule, target_date)
    estimated_hours = round(sum((item.get("duration_minutes") or 0) for item in schedule) / 60, 2)
    summary = f"{len(schedule)} scheduled item{'s' if len(schedule) != 1 else ''}, about {estimated_hours}h planned, {len(risks)} risk{'s' if len(risks) != 1 else ''}."
    entry = DailyAssistantEntry(
        entry_date=target_date,
        kind="morning",
        summary=summary,
        schedule_json=_dump(schedule),
        explanations_json=_dump(explanations),
        risks_json=_dump(risks),
        estimated_hours=estimated_hours,
    )
    db.session.add(entry)
    db.session.commit()
    return serialize_entry(entry)


def plan_blocks_for_date(target_date):
    events = PlanningEvent.query.order_by(
        PlanningEvent.status.asc(),
        PlanningEvent.deadline.is_(None),
        PlanningEvent.deadline.asc(),
        PlanningEvent.planned_start.asc(),
    ).limit(120).all()
    blocks = PlanningEngine(events, lambda event: _json(event.metadata_json, {}), today=target_date).build()
    return blocks["today"] or blocks["week"][:5]


def run_daily_assistant_cycle(now=None):
    now = parse_datetime(now) or datetime.utcnow()
    result = {"ok": True, "date": now.date().isoformat(), "created": []}
    if now.time() >= MORNING_BRIEFING_AT and not assistant_entry_exists(now.date(), "morning"):
        result["morning"] = generate_morning_briefing(now.date())
        result["created"].append("morning")
    if now.time() >= EVENING_CHECKIN_AT and not assistant_entry_exists(now.date(), "evening_prompt"):
        result["evening"] = evening_checkin_prompt(now.date())
        result["created"].append("evening_prompt")
    return result


def assistant_entry_exists(target_date, kind):
    return (
        DailyAssistantEntry.query.filter_by(entry_date=target_date, kind=kind)
        .order_by(DailyAssistantEntry.created_at.desc())
        .first()
        is not None
    )


def evening_checkin_prompt(target_date=None):
    target_date = parse_date(target_date) or date.today()
    board = planning_board()
    questions = list(EVENING_QUESTIONS)
    questions.extend(item["question"] for item in board["question_queue"][:5])
    entry = DailyAssistantEntry(
        entry_date=target_date,
        kind="evening_prompt",
        summary="Evening check-in questions generated.",
        questions_json=_dump(questions),
    )
    db.session.add(entry)
    db.session.commit()
    return serialize_entry(entry)


def submit_evening_checkin(data, target_date=None):
    target_date = parse_date(target_date or data.get("date")) or date.today()
    responses = normalize_responses(data)
    replans = apply_evening_replan(responses)
    follow_up = generate_morning_briefing(target_date + timedelta(days=1))
    entry = DailyAssistantEntry(
        entry_date=target_date,
        kind="evening_response",
        summary=evening_summary(responses, replans),
        questions_json=_dump(EVENING_QUESTIONS),
        responses_json=_dump_object(responses),
        replans_json=_dump(replans),
        estimated_hours=float(responses.get("hours_worked") or 0),
    )
    db.session.add(entry)
    db.session.commit()
    return {"ok": True, "entry": serialize_entry(entry), "replans": replans, "next_morning": follow_up}


def latest_daily_assistant_summary(target_date=None):
    target_date = parse_date(target_date) or date.today()
    latest_morning = (
        DailyAssistantEntry.query.filter_by(entry_date=target_date, kind="morning")
        .order_by(DailyAssistantEntry.created_at.desc())
        .first()
    )
    latest_evening = (
        DailyAssistantEntry.query.filter(DailyAssistantEntry.entry_date <= target_date)
        .filter(DailyAssistantEntry.kind.in_(["evening_prompt", "evening_response"]))
        .order_by(DailyAssistantEntry.created_at.desc())
        .first()
    )
    result = {
        "morning": serialize_entry(latest_morning) if latest_morning else generate_morning_briefing(target_date),
        "evening": serialize_entry(latest_evening) if latest_evening else evening_checkin_prompt(target_date),
    }
    result["history_count"] = DailyAssistantEntry.query.count()
    return result


def normalize_schedule_item(item):
    start = item.get("start") or item.get("planned_start")
    event_id = item.get("event_id") or item.get("id")
    event = db.session.get(PlanningEvent, int(event_id)) if event_id else None
    return {
        "event_id": event_id,
        "title": item.get("title") or (event.title if event else ""),
        "project": item.get("project") or (event.project if event else "") or "",
        "event_type": item.get("event_type") or (event.event_type if event else "") or "",
        "start": start,
        "duration_minutes": int(item.get("duration_minutes") or item.get("planned_minutes") or (event.planned_minutes if event else 45) or 45),
        "deadline": item.get("deadline") or (event.deadline.isoformat() if event and event.deadline else None),
        "priority": item.get("priority") or (event.priority if event else "") or "normal",
        "status": item.get("status") or (event.status if event else "") or "planned",
        "next_action": item.get("next_action") or item.get("work_left") or (event.work_left if event else "") or "",
    }


def explain_selection(item):
    reasons = []
    if item.get("deadline"):
        reasons.append("has a deadline")
    if item.get("priority") in {"high", "urgent"}:
        reasons.append(f"is {item['priority']} priority")
    if item.get("event_type") in {"email", "hackathon", "repo", "learning", "learning_video"}:
        reasons.append(f"comes from {item['event_type']} intelligence")
    if not reasons:
        reasons.append("is the next open planning item")
    return {"event_id": item.get("event_id"), "title": item.get("title"), "why": "; ".join(reasons)}


def identify_risks(board, schedule, target_date):
    risks = []
    scheduled_ids = {item.get("event_id") for item in schedule}
    for event in board["events"]:
        deadline = parse_datetime(event.get("deadline"))
        if deadline and deadline.date() < target_date and event.get("status") not in {"completed", "done"}:
            risks.append({"event_id": event["id"], "title": event["title"], "risk": "overdue"})
        elif deadline and deadline.date() <= target_date + timedelta(days=1) and event["id"] not in scheduled_ids:
            risks.append({"event_id": event["id"], "title": event["title"], "risk": "due soon but not scheduled"})
        if event.get("status") == "blocked":
            risks.append({"event_id": event["id"], "title": event["title"], "risk": "blocked"})
    planned_minutes = sum((item.get("duration_minutes") or 0) for item in schedule)
    if planned_minutes > 8 * 60:
        risks.append({"event_id": None, "title": "Daily capacity", "risk": "planned work exceeds 8 hours"})
    return risks[:12]


def normalize_responses(data):
    return {
        "completed": as_list(data.get("completed") or data.get("completed_event_ids") or data.get("completed_titles")),
        "blocked": as_list(data.get("blocked") or data.get("blocked_event_ids")),
        "blockers": str(data.get("blockers") or data.get("what_blocked_you") or "").strip(),
        "hours_worked": parse_float(data.get("hours_worked")),
        "move_deadlines": data.get("move_deadlines") or {},
        "modify_priorities": data.get("modify_priorities") or {},
        "notes": str(data.get("notes") or "").strip(),
    }


def apply_evening_replan(responses):
    replans = []
    for event in match_events(responses["completed"]):
        result = update_event_progress(
            event.id,
            {
                "status": "completed",
                "progress_note": responses["notes"] or "Marked complete from evening check-in.",
            },
        )
        replans.append({"event_id": event.id, "action": "completed", "ok": result.get("ok", False)})

    blocker_note = responses["blockers"] or "Blocked from evening check-in."
    for event in match_events(responses["blocked"]):
        result = update_event_progress(
            event.id,
            {
                "status": "blocked",
                "progress_note": blocker_note,
            },
        )
        replans.append({"event_id": event.id, "action": "blocked", "ok": result.get("ok", False)})

    for event_id, value in dict(responses["move_deadlines"] or {}).items():
        event = db.session.get(PlanningEvent, int(event_id))
        if not event:
            continue
        new_deadline = parse_datetime(value)
        if new_deadline:
            event.deadline = new_deadline
            event.planned_start = min(event.planned_start or new_deadline, new_deadline)
            append_event_history(event, f"Deadline moved to {new_deadline.isoformat()} from evening check-in.")
            replans.append({"event_id": event.id, "action": "deadline_moved", "deadline": new_deadline.isoformat(), "ok": True})

    for event_id, priority in dict(responses["modify_priorities"] or {}).items():
        event = db.session.get(PlanningEvent, int(event_id))
        if not event:
            continue
        event.priority = str(priority or event.priority).lower()[:40]
        append_event_history(event, f"Priority changed to {event.priority} from evening check-in.")
        replans.append({"event_id": event.id, "action": "priority_modified", "priority": event.priority, "ok": True})

    hours = responses.get("hours_worked")
    if hours:
        for event in match_events(responses["completed"] + responses["blocked"]):
            append_event_history(event, f"Evening check-in logged {hours}h worked.")
    db.session.commit()
    planning_board()
    return replans


def match_events(values):
    events = []
    for value in values:
        if isinstance(value, int) or str(value).isdigit():
            event = db.session.get(PlanningEvent, int(value))
        else:
            event = PlanningEvent.query.filter(PlanningEvent.title.ilike(f"%{str(value).strip()}%")).first()
        if event and event not in events:
            events.append(event)
    return events


def append_event_history(event, note):
    metadata = _json(event.metadata_json, {})
    history = metadata.get("assistant_history") or []
    history.append({"at": datetime.utcnow().isoformat(), "note": note})
    metadata["assistant_history"] = history
    event.metadata_json = _dump_object(metadata)


def evening_summary(responses, replans):
    completed = len(responses.get("completed") or [])
    blocked = len(responses.get("blocked") or [])
    hours = responses.get("hours_worked") or 0
    return f"Completed {completed}, blocked {blocked}, logged {hours}h, applied {len(replans)} replans."


def as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [part.strip() for part in str(value).split(",") if part.strip()]


def parse_float(value):
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def parse_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


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
            return datetime.combine(date.fromisoformat(raw), datetime.min.time()).replace(hour=17)
        except ValueError:
            return None


def serialize_entry(entry):
    if entry is None:
        return None
    return {
        "id": entry.id,
        "date": entry.entry_date.isoformat(),
        "kind": entry.kind,
        "summary": entry.summary or "",
        "schedule": _json(entry.schedule_json),
        "explanations": _json(entry.explanations_json),
        "risks": _json(entry.risks_json),
        "questions": _json(entry.questions_json),
        "responses": _json(entry.responses_json, {}),
        "replans": _json(entry.replans_json),
        "estimated_hours": entry.estimated_hours,
        "created_at": entry.created_at.isoformat(),
    }
