import json
import re
from datetime import date, datetime, time, timedelta

from app.models import LearningItem, LifeItem, LifeItemRelation, PlanningEvent, db


LEARNING_TYPES = {"course", "video", "book", "article", "practice", "project"}
DONE_STATUSES = {"completed", "done"}


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


def clean(value, limit=500):
    return str(value or "").strip()[:limit]


def evening_time(target=None):
    target = target or date.today()
    return datetime.combine(target, time(hour=18))


def upsert_learning_item(data):
    source_key = clean(data.get("source_key") or "", 240)
    item = None
    if source_key:
        item = LearningItem.query.join(LifeItem, LearningItem.life_item_id == LifeItem.id).filter(LifeItem.source_key == source_key).first()
    if item is None and data.get("id"):
        item = db.session.get(LearningItem, int(data["id"]))
    if item is None:
        item = LearningItem()
        db.session.add(item)

    item_type = clean(data.get("item_type") or data.get("type") or item.item_type or "course", 40).lower()
    item.item_type = item_type if item_type in LEARNING_TYPES else "course"
    item.title = clean(data.get("title") or item.title, 240)
    item.source_url = clean(data.get("source_url") or item.source_url, 500)
    item.project = clean(data.get("project") or item.project, 180)
    item.status = clean(data.get("status") or item.status or "not_started", 40)
    item.completion = normalize_completion(data.get("completion", item.completion))
    item.notes = merge_notes(item.notes, data.get("notes"))
    item.revision_json = _dump(data.get("revision") if "revision" in data else _json(item.revision_json))
    item.quiz_json = _dump(data.get("quiz") if "quiz" in data else _json(item.quiz_json))
    item.weak_topics_json = _dump(data.get("weak_topics") if "weak_topics" in data else _json(item.weak_topics_json))
    item.projects_json = _dump(data.get("projects") if "projects" in data else _json(item.projects_json))
    item.scheduled_at = parse_datetime(data.get("scheduled_at")) or item.scheduled_at or evening_time()
    item.deadline = parse_datetime(data.get("deadline")) or item.deadline
    item.estimated_minutes = normalize_minutes(data.get("estimated_minutes"), item.estimated_minutes)
    item.last_reviewed_at = parse_datetime(data.get("last_reviewed_at")) or item.last_reviewed_at
    item.next_revision_at = parse_datetime(data.get("next_revision_at")) or item.next_revision_at or next_revision_time(item)
    item.evening_prompt_at = parse_datetime(data.get("evening_prompt_at")) or item.evening_prompt_at or evening_time()
    link_learning_life_item(item, source_key)
    db.session.flush()
    upsert_learning_event(item)
    db.session.commit()
    return {"ok": True, "item": serialize_learning_item(item)}


def record_learning_progress(item_id, data):
    item = db.session.get(LearningItem, int(item_id))
    if item is None:
        return {"ok": False, "message": "Learning item not found."}
    note = clean(data.get("notes") or data.get("progress_note"), 2000)
    completed = bool(data.get("completed"))
    if completed or clean(data.get("status"), 40) in DONE_STATUSES:
        item.completion = 1.0
        item.status = "completed"
    elif "completion" in data:
        item.completion = normalize_completion(data.get("completion"))
        item.status = "in_progress" if item.completion < 1 else "completed"
    elif note:
        item.completion = min(0.95, max(item.completion or 0.0, (item.completion or 0.0) + 0.25))
        item.status = "in_progress"
    item.notes = merge_notes(item.notes, note)
    item.weak_topics_json = _dump(merge_lists(_json(item.weak_topics_json), data.get("weak_topics") or extract_weak_topics(note)))
    item.projects_json = _dump(merge_lists(_json(item.projects_json), data.get("projects") or extract_projects_using_knowledge(note)))
    item.quiz_json = _dump(merge_lists(_json(item.quiz_json), data.get("quiz") or extract_quiz_items(note)))
    item.revision_json = _dump(merge_lists(_json(item.revision_json), data.get("revision") or []))
    item.last_reviewed_at = datetime.utcnow()
    item.next_revision_at = next_revision_time(item)
    if item.completion < 1.0:
        item.scheduled_at = rescheduled_time(item)
    update_life_item_from_learning(item)
    upsert_learning_event(item)
    db.session.commit()
    return {"ok": True, "item": serialize_learning_item(item)}


def sync_learning_item_from_event(event, progress_note=""):
    metadata = _json(event.metadata_json, {})
    learning_item_id = metadata.get("learning_item_id")
    if not learning_item_id:
        return None
    payload = {"progress_note": progress_note}
    if event.status in DONE_STATUSES:
        payload["completed"] = True
    elif event.status == "in_progress":
        payload["status"] = "in_progress"
    if event.work_done and not payload.get("progress_note"):
        payload["progress_note"] = event.work_done
    return record_learning_progress(learning_item_id, payload)


def generate_events_from_learning_items():
    reschedule_unfinished_learning()
    count = 0
    for item in LearningItem.query.filter(LearningItem.status.notin_(["completed", "done"])).limit(80).all():
        upsert_learning_event(item)
        count += 1
    db.session.commit()
    return {"ok": True, "events": count}


def upsert_learning_event(item):
    source_key = f"learning_item:{item.id}"
    event = PlanningEvent.query.filter_by(source_key=source_key).first()
    if event is None:
        event = PlanningEvent(source_key=source_key, source="learning_intelligence")
        db.session.add(event)
    event.event_type = "learning_video" if item.item_type == "video" else "learning"
    event.title = item.title
    event.project = item.project or item.item_type.title()
    event.idea = item.notes or item.source_url or ""
    event.deadline = item.deadline or item.next_revision_at
    event.planned_start = item.scheduled_at or evening_time()
    event.planned_minutes = item.estimated_minutes
    event.priority = "high" if item.deadline and item.deadline.date() <= date.today() + timedelta(days=2) else "normal"
    event.status = "completed" if item.completion >= 1.0 else item.status if item.status != "not_started" else "planned"
    event.work_done = summarize_learning_done(item)
    event.work_left = summarize_learning_left(item)
    event.next_question = evening_question(item)
    event.metadata_json = _dump_object(
        {
            "learning_item_id": item.id,
            "learning_type": item.item_type,
            "progress": item.completion,
            "estimated_hours": round((item.estimated_minutes or 45) / 60, 2),
            "weak_topics": _json(item.weak_topics_json),
            "projects_using_knowledge": _json(item.projects_json),
        }
    )
    return event


def reschedule_unfinished_learning(now=None):
    now = now or datetime.utcnow()
    moved = 0
    for item in LearningItem.query.filter(LearningItem.completion < 1.0).all():
        if item.scheduled_at and item.scheduled_at < now:
            item.scheduled_at = rescheduled_time(item, now)
            moved += 1
    return {"ok": True, "rescheduled": moved}


def evening_questions(now=None):
    items = (
        LearningItem.query.filter(LearningItem.status.notin_(["completed", "done"]))
        .order_by(LearningItem.scheduled_at.asc())
        .limit(12)
        .all()
    )
    return [evening_question(item) for item in items]


def learning_summary():
    generate_events_from_learning_items()
    items = LearningItem.query.order_by(LearningItem.updated_at.desc()).limit(50).all()
    unfinished = [item for item in items if item.completion < 1.0]
    weak_topics = []
    for item in items:
        weak_topics.extend(_json(item.weak_topics_json))
    return {
        "items": [serialize_learning_item(item) for item in items],
        "counts": {
            "total": len(items),
            "unfinished": len(unfinished),
            "completed": len([item for item in items if item.completion >= 1.0]),
            "courses": len([item for item in items if item.item_type == "course"]),
            "videos": len([item for item in items if item.item_type == "video"]),
            "books": len([item for item in items if item.item_type == "book"]),
            "articles": len([item for item in items if item.item_type == "article"]),
            "practice": len([item for item in items if item.item_type == "practice"]),
            "projects": len([item for item in items if item.item_type == "project"]),
        },
        "evening_questions": evening_questions(),
        "weak_topics": list(dict.fromkeys(weak_topics))[:12],
    }


def link_learning_life_item(item, source_key=""):
    if item.life_item is None:
        key = source_key or f"learning:{item.item_type}:{slugify(item.title)}"
        life = LifeItem.query.filter_by(source_key=key).first()
        if life is None:
            life = LifeItem(source_key=key)
            db.session.add(life)
        item.life_item = life
    update_life_item_from_learning(item)
    link_learning_to_project_items(item)


def update_life_item_from_learning(item):
    if item.life_item is None:
        return
    item.life_item.title = item.title
    item.life_item.description = item.notes or f"{item.item_type.title()} tracked by Learning Intelligence."
    item.life_item.category = "learning"
    item.life_item.priority = "normal"
    item.life_item.status = "completed" if item.completion >= 1.0 else "open"
    item.life_item.deadline = item.deadline or item.next_revision_at
    item.life_item.estimated_hours = round((item.estimated_minutes or 45) / 60, 2)
    item.life_item.progress = round((item.completion or 0.0) * 100, 2)
    item.life_item.energy_level = "medium"
    item.life_item.difficulty = "medium" if _json(item.weak_topics_json) else "normal"
    item.life_item.repository = ""
    item.life_item.ai_summary = summarize_learning_done(item)
    item.life_item.next_action = summarize_learning_left(item)
    item.life_item.tags_json = _dump([item.item_type, item.project or "", *(_json(item.weak_topics_json))])
    item.life_item.metadata_json = _dump_object(
        {
            "learning_item_id": item.id,
            "source_url": item.source_url,
            "completion": item.completion,
            "revision": _json(item.revision_json),
            "quiz": _json(item.quiz_json),
            "weak_topics": _json(item.weak_topics_json),
            "projects_using_knowledge": _json(item.projects_json),
        }
    )


def link_learning_to_project_items(item):
    if item.life_item is None:
        return
    project_names = [item.project] + _json(item.projects_json)
    signals = {name.lower() for name in project_names if name}
    if not signals:
        return
    for candidate in LifeItem.query.filter(LifeItem.id != item.life_item.id).limit(200).all():
        haystack = " ".join([candidate.title or "", candidate.description or "", candidate.tags_json or ""]).lower()
        if not any(signal in haystack for signal in signals):
            continue
        exists = LifeItemRelation.query.filter_by(
            source_item_id=item.life_item.id,
            target_item_id=candidate.id,
            relation_type="uses_learning",
        ).first()
        if exists:
            continue
        db.session.add(
            LifeItemRelation(
                source_item=item.life_item,
                target_item=candidate,
                relation_type="uses_learning",
                strength=0.75,
                reason=f"Learning item supports project context: {', '.join(sorted(signals)[:3])}",
                metadata_json=_dump_object({"learning_item_id": item.id, "signals": sorted(signals)}),
            )
        )


def evening_question(item):
    if item.item_type == "video":
        return f"Which videos did you complete for {item.title}? What notes did you take?"
    if item.item_type == "course":
        return f"What course module did you finish for {item.title}? What notes or weak topics should I remember?"
    if item.item_type == "book":
        return f"What pages or chapter did you complete in {item.title}? What should be revised?"
    if item.item_type == "article":
        return f"What did you learn from {item.title}? Any notes, quiz ideas, or weak topics?"
    if item.item_type == "practice":
        return f"What practice did you complete for {item.title}? Which weak topics remain?"
    return f"What progress did you make on learning project {item.title}, and what should be rescheduled?"


def summarize_learning_done(item):
    if item.completion >= 1.0:
        return f"Completed {item.item_type}: {item.title}."
    if item.notes:
        return item.notes[:700]
    return f"{round((item.completion or 0.0) * 100)}% complete."


def summarize_learning_left(item):
    weak = _json(item.weak_topics_json)
    if item.completion >= 1.0:
        return "Schedule revision or apply this knowledge in a project."
    if weak:
        return f"Review weak topics: {', '.join(weak[:4])}."
    return f"Continue {item.item_type}: {item.title}."


def normalize_completion(value):
    try:
        raw = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if raw > 1:
        raw = raw / 100
    return max(0.0, min(1.0, raw))


def normalize_minutes(value, fallback=45):
    try:
        minutes = int(value or fallback or 45)
    except (TypeError, ValueError):
        minutes = fallback or 45
    return max(5, min(480, minutes))


def next_revision_time(item):
    if item.completion >= 1.0:
        return evening_time(date.today() + timedelta(days=2))
    return evening_time(date.today() + timedelta(days=1))


def rescheduled_time(item, now=None):
    now = now or datetime.utcnow()
    target = now.date() + timedelta(days=1)
    if item.deadline and item.deadline.date() <= target:
        target = now.date()
    return evening_time(target)


def merge_notes(existing, incoming):
    incoming = clean(incoming, 2000)
    if not incoming:
        return existing or ""
    if not existing:
        return incoming
    if incoming in existing:
        return existing
    return f"{existing}\n{datetime.utcnow().isoformat()}: {incoming}"[:5000]


def merge_lists(existing, incoming):
    values = existing or []
    if isinstance(incoming, str):
        incoming = [incoming]
    for item in incoming or []:
        text = clean(item, 200)
        if text and text not in values:
            values.append(text)
    return values[:30]


def extract_weak_topics(note):
    if not note:
        return []
    topics = []
    for pattern in [r"weak(?: topics?)?[:\-]\s*([^.;\n]+)", r"revise[:\-]\s*([^.;\n]+)", r"stuck on\s+([^.;\n]+)"]:
        for match in re.finditer(pattern, note, re.I):
            topics.extend(part.strip() for part in re.split(r",|/", match.group(1)) if part.strip())
    return topics[:8]


def extract_projects_using_knowledge(note):
    if not note:
        return []
    projects = []
    for pattern in [r"project[:\-]\s*([^.;\n]+)", r"using this (?:in|for)\s+([^.;\n]+)"]:
        for match in re.finditer(pattern, note, re.I):
            projects.append(match.group(1).strip())
    return projects[:8]


def extract_quiz_items(note):
    if not note:
        return []
    items = []
    for match in re.finditer(r"quiz[:\-]\s*([^.;\n]+)", note, re.I):
        items.append(match.group(1).strip())
    return items[:8]


def parse_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(raw), time(hour=18))
        except ValueError:
            return None


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")[:120] or "learning"


def serialize_learning_item(item):
    return {
        "id": item.id,
        "life_item_id": item.life_item_id,
        "item_type": item.item_type,
        "title": item.title,
        "source_url": item.source_url or "",
        "project": item.project or "",
        "status": item.status,
        "completion": item.completion,
        "notes": item.notes or "",
        "revision": _json(item.revision_json),
        "quiz": _json(item.quiz_json),
        "weak_topics": _json(item.weak_topics_json),
        "projects": _json(item.projects_json),
        "scheduled_at": item.scheduled_at.isoformat() if item.scheduled_at else None,
        "deadline": item.deadline.isoformat() if item.deadline else None,
        "estimated_minutes": item.estimated_minutes,
        "last_reviewed_at": item.last_reviewed_at.isoformat() if item.last_reviewed_at else None,
        "next_revision_at": item.next_revision_at.isoformat() if item.next_revision_at else None,
        "evening_prompt": evening_question(item),
    }
