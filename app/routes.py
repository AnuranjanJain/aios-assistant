from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

from app.models import ActivityEvent, ConnectorRun, HackathonUpdate, InboxItem, Opportunity, Reminder, db
from app.services.agent_ingest import ingest_message as ingest_agent_message
from app.services.ai_classifier import get_classifier
from app.services.api_auth import has_valid_api_token
from app.services.auth import clear_pin, has_pin, set_pin, verify_pin
from app.services.connectors import list_connectors, run_connector
from app.services.data_pipelines import SUPPORTED_IMPORTS, import_source_file
from app.services.daily_planner import build_daily_plan
from app.services.hackathons import ingest_hackathon_signal, serialize_hackathon
from app.services.settings import SETTING_KEYS, apply_settings, get_effective_config
from app.services.wellbeing import summarize_activity
from app.services.workers import list_worker_status, start_worker, stop_worker


bp = Blueprint("main", __name__)


@bp.before_app_request
def require_ui_auth():
    if request.method == "OPTIONS":
        return None

    if not has_pin():
        return None

    if session.get("is_unlocked"):
        return None

    if request.endpoint in {"main.login", "main.unlock"}:
        return None

    if request.path.startswith("/static/"):
        return None

    if request.path.startswith("/api/") and has_valid_api_token(request, current_app.config):
        return None

    if request.path.startswith("/api/"):
        return jsonify({"error": "locked"}), 401

    return redirect(url_for("main.login", next=request.full_path))


@bp.after_app_request
def add_local_api_headers(response):
    origin = request.headers.get("Origin")
    if origin and origin.startswith(("http://127.0.0.1:", "http://localhost:")):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-AiOS-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@bp.get("/login")
def login():
    return render_template("login.html", has_pin=has_pin(), error="", next_url=request.args.get("next", ""))


@bp.post("/login")
def unlock():
    pin = request.form.get("pin", "")
    next_url = request.form.get("next") or url_for("main.dashboard")

    if not has_pin():
        if len(pin) < 4:
            return render_template("login.html", has_pin=False, error="Use at least 4 digits.", next_url=next_url), 400
        set_pin(pin)
        db.session.commit()
        session["is_unlocked"] = True
        return redirect(next_url)

    if verify_pin(pin):
        session["is_unlocked"] = True
        return redirect(next_url)

    return render_template("login.html", has_pin=True, error="Incorrect PIN.", next_url=next_url), 401


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@bp.get("/")
def dashboard():
    context = build_dashboard_context()
    return render_template("dashboard.html", **context)


@bp.get("/mobile")
def mobile_dashboard():
    context = build_dashboard_context()
    return render_template("mobile.html", **context)


@bp.get("/sources")
def sources():
    return render_template("sources.html", result=None)


@bp.get("/connectors")
def connectors():
    runs = ConnectorRun.query.order_by(ConnectorRun.created_at.desc()).limit(12).all()
    return render_template(
        "connectors.html",
        connectors=list_connectors(get_effective_config(current_app.config)),
        runs=runs,
        result=None,
    )


@bp.post("/connectors/<connector_id>/run")
def run_connector_route(connector_id):
    result = run_connector(
        connector_id,
        get_effective_config(current_app.config),
        classifier=build_classifier(),
        provider=get_effective_config(current_app.config)["AI_PROVIDER"],
        model=get_effective_config(current_app.config)["OLLAMA_MODEL"],
    )
    db.session.commit()

    runs = ConnectorRun.query.order_by(ConnectorRun.created_at.desc()).limit(12).all()
    return render_template(
        "connectors.html",
        connectors=list_connectors(get_effective_config(current_app.config)),
        runs=runs,
        result=result,
    )


@bp.get("/settings")
def settings():
    values = get_effective_config(current_app.config)
    return render_template("settings.html", keys=SETTING_KEYS, values=values, saved=False, pin_enabled=has_pin())


@bp.get("/workers")
def workers():
    return render_template("workers.html", workers=list_worker_status(), result=None)


@bp.post("/workers/<worker_id>/start")
def start_worker_route(worker_id):
    result = start_worker(worker_id)
    return render_template("workers.html", workers=list_worker_status(), result=result)


@bp.post("/workers/<worker_id>/stop")
def stop_worker_route(worker_id):
    result = stop_worker(worker_id)
    return render_template("workers.html", workers=list_worker_status(), result=result)


@bp.post("/settings")
def save_settings():
    pin_action = request.form.get("pin_action", "")
    new_pin = request.form.get("new_pin", "")

    if pin_action == "set_pin" and new_pin:
        set_pin(new_pin)
    elif pin_action == "clear_pin":
        clear_pin()

    apply_settings(request.form)
    db.session.commit()
    values = get_effective_config(current_app.config)
    return render_template("settings.html", keys=SETTING_KEYS, values=values, saved=True, pin_enabled=has_pin())


@bp.post("/sources/import")
def import_source():
    upload = request.files.get("source_file")
    if not upload or not upload.filename:
        return render_template("sources.html", result={"imported": 0, "filename": "No file selected."}), 400

    filename = secure_filename(upload.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_IMPORTS:
        return render_template("sources.html", result={"imported": 0, "filename": f"Unsupported file type: {suffix}"}), 400

    import_dir = Path("imports")
    import_dir.mkdir(exist_ok=True)
    import_path = import_dir / filename
    upload.save(import_path)

    imported = import_source_file(
        import_path,
        classifier=build_classifier(),
        provider=get_effective_config(current_app.config)["AI_PROVIDER"],
        model=get_effective_config(current_app.config)["OLLAMA_MODEL"],
    )
    db.session.commit()

    return render_template(
        "sources.html",
        result={"imported": len(imported), "filename": filename},
    )


def build_dashboard_context():
    opportunities = Opportunity.query.order_by(Opportunity.updated_at.desc()).all()
    reminders = Reminder.query.order_by(Reminder.due_at.asc()).all()
    inbox_items = InboxItem.query.order_by(InboxItem.created_at.desc()).limit(8).all()
    activity_events = ActivityEvent.query.order_by(ActivityEvent.created_at.desc()).limit(5).all()
    connector_runs = ConnectorRun.query.order_by(ConnectorRun.created_at.desc()).limit(5).all()
    plan = build_daily_plan(opportunities, reminders)
    stats = build_dashboard_stats(opportunities, reminders, inbox_items, activity_events)

    return {
        "opportunities": opportunities,
        "reminders": reminders,
        "inbox_items": inbox_items,
        "activity_events": activity_events,
        "connector_runs": connector_runs,
        "plan": plan,
        "stats": stats,
    }


@bp.post("/ingest")
def ingest_message():
    subject = request.form.get("subject", "").strip()
    sender = request.form.get("sender", "").strip()
    body = request.form.get("body", "").strip()

    if not subject:
        return redirect(url_for("main.dashboard"))

    classifier = build_classifier()
    ingest_agent_message(
        sender=sender,
        subject=subject,
        body=body,
        source="manual inbox",
        classifier=classifier,
        provider=get_effective_config(current_app.config)["AI_PROVIDER"],
        model=get_effective_config(current_app.config)["OLLAMA_MODEL"],
    )

    db.session.commit()
    return redirect(url_for("main.dashboard"))


@bp.post("/reminders/<int:reminder_id>/done")
def complete_reminder(reminder_id):
    reminder = Reminder.query.get_or_404(reminder_id)
    reminder.is_done = True
    reminder.is_read = True
    db.session.commit()
    return redirect(url_for("main.dashboard"))


@bp.post("/reminders/<int:reminder_id>/read")
def mark_reminder_read(reminder_id):
    reminder = Reminder.query.get_or_404(reminder_id)
    reminder.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for("main.dashboard"))


@bp.post("/seed")
def seed_demo():
    examples = [
        ("jobs@example.com", "Your application received for ML Intern", "Thank you for applying."),
        ("talent@example.com", "Interview schedule for Backend Intern", "Please join your technical round tomorrow."),
        ("team@devfolio.co", "Hackathon submission deadline reminder", "Your prototype is due this weekend."),
    ]

    classifier = build_classifier()
    for sender, subject, body in examples:
        ingest_agent_message(
            sender=sender,
            subject=subject,
            body=body,
            source="demo seed",
            classifier=classifier,
            provider=get_effective_config(current_app.config)["AI_PROVIDER"],
            model=get_effective_config(current_app.config)["OLLAMA_MODEL"],
        )

    db.session.commit()
    return redirect(url_for("main.dashboard"))


@bp.get("/api/plan")
def api_plan():
    opportunities = Opportunity.query.all()
    reminders = Reminder.query.all()
    return jsonify(build_daily_plan(opportunities, reminders))


@bp.post("/api/ingest-email")
@bp.post("/api/track-job")
@bp.post("/api/track-hackathon")
def api_ingest_message():
    data = request.get_json(silent=True) or {}
    subject = (data.get("subject") or data.get("title") or "").strip()
    sender = (data.get("sender") or data.get("organization") or "").strip()
    body = (data.get("body") or data.get("content") or data.get("notes") or "").strip()
    source = (data.get("source") or "local api").strip()

    if not subject:
        return jsonify({"error": "subject or title is required"}), 400

    result = ingest_agent_message(
        sender=sender,
        subject=subject,
        body=body,
        source=source,
        classifier=build_classifier(),
        provider=get_effective_config(current_app.config)["AI_PROVIDER"],
        model=get_effective_config(current_app.config)["OLLAMA_MODEL"],
    )
    db.session.commit()

    opportunity = result["opportunity"]
    return jsonify(
        {
            "classification": result["classification"].__dict__,
            "opportunity_id": opportunity.id if opportunity else None,
            "inbox_item_id": result["inbox_item"].id,
        }
    ), 201


@bp.get("/api/hackathons")
def api_hackathons():
    hackathons = (
        Opportunity.query.filter_by(kind="hackathon")
        .order_by(Opportunity.updated_at.desc())
        .all()
    )
    connector_runs = (
        ConnectorRun.query.filter(
            ConnectorRun.connector_id.in_(["gmail", "hackathon_platforms"])
        )
        .order_by(ConnectorRun.created_at.desc())
        .limit(8)
        .all()
    )
    return jsonify(
        {
            "hackathons": [serialize_hackathon(item) for item in hackathons],
            "connectors": [serialize_connector_run(item) for item in connector_runs],
            "unread_updates": HackathonUpdate.query.filter_by(is_read=False).count(),
            "updated_at": datetime.utcnow().isoformat(),
        }
    )


@bp.post("/api/hackathons/capture")
def api_capture_hackathon():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or data.get("subject") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    opportunity, update, created = ingest_hackathon_signal(
        title=title,
        source=(data.get("source") or "local api").strip(),
        body=(data.get("body") or data.get("content") or "").strip(),
        organization=(data.get("organization") or "").strip(),
        platform=(data.get("platform") or "").strip(),
        url=(data.get("url") or "").strip(),
        status=(data.get("status") or "").strip(),
        deadline=data.get("deadline"),
        external_id=(data.get("external_id") or "").strip(),
        occurred_at=data.get("occurred_at"),
    )
    db.session.commit()
    return jsonify(
        {
            "created": created,
            "hackathon": serialize_hackathon(opportunity),
            "update_id": update.id,
        }
    ), 201 if created else 200


@bp.post("/api/hackathons/refresh")
def api_refresh_hackathons():
    values = get_effective_config(current_app.config)
    results = []
    for connector_id in ("gmail", "hackathon_platforms"):
        result = run_connector(
            connector_id,
            values,
            classifier=build_classifier(),
            provider=values["AI_PROVIDER"],
            model=values["OLLAMA_MODEL"],
        )
        results.append(result.__dict__)
    db.session.commit()
    return jsonify({"ok": True, "connectors": results})


@bp.post("/api/hackathon-updates/<int:update_id>/read")
def api_mark_hackathon_update_read(update_id):
    update = HackathonUpdate.query.get_or_404(update_id)
    update.is_read = True
    db.session.commit()
    return jsonify({"ok": True, "update_id": update.id})


@bp.post("/api/wellbeing/activity")
def api_wellbeing_activity():
    data = request.get_json(silent=True) or {}
    category = (data.get("category") or "unknown").strip().lower()
    duration_minutes = int(data.get("duration_minutes") or 0)
    planned_task = (data.get("planned_task") or "").strip()
    actual_task = (data.get("actual_task") or "").strip()
    summary = summarize_activity(category, duration_minutes, planned_task, actual_task)

    event = ActivityEvent(
        source=(data.get("source") or "local api").strip(),
        app_name=(data.get("app_name") or "").strip(),
        category=category,
        planned_task=planned_task,
        actual_task=actual_task,
        duration_minutes=duration_minutes,
        agent_summary=summary,
    )
    db.session.add(event)
    db.session.commit()

    return jsonify(
        {
            "activity_event_id": event.id,
            "category": event.category,
            "duration_minutes": event.duration_minutes,
            "agent_summary": event.agent_summary,
        }
    ), 201


@bp.get("/api/today")
def api_today():
    opportunities = Opportunity.query.order_by(Opportunity.updated_at.desc()).all()
    reminders = Reminder.query.order_by(Reminder.due_at.asc()).all()
    activities = ActivityEvent.query.order_by(ActivityEvent.created_at.desc()).limit(5).all()

    return jsonify(
        {
            "plan": build_daily_plan(opportunities, reminders),
            "opportunities": [serialize_opportunity(item) for item in opportunities],
            "reminders": [serialize_reminder(item) for item in reminders],
            "recent_activity": [serialize_activity(item) for item in activities],
        }
    )


@bp.get("/api/live")
def api_live():
    context = build_dashboard_context()
    latest_opportunity = context["opportunities"][0] if context["opportunities"] else None
    latest_activity = context["activity_events"][0] if context["activity_events"] else None
    latest_connector = context["connector_runs"][0] if context["connector_runs"] else None

    return jsonify(
        {
            "plan": context["plan"],
            "stats": context["stats"],
            "latest_opportunity": serialize_opportunity(latest_opportunity) if latest_opportunity else None,
            "latest_activity": serialize_activity(latest_activity) if latest_activity else None,
            "reminders": [serialize_reminder(item) for item in context["reminders"][:5]],
            "opportunities": [serialize_opportunity(item) for item in context["opportunities"][:6]],
            "activities": [serialize_activity(item) for item in context["activity_events"][:5]],
            "inbox_items": [serialize_inbox_item(item) for item in context["inbox_items"][:6]],
            "connector_runs": [serialize_connector_run(item) for item in context["connector_runs"][:5]],
            "latest_connector": serialize_connector_run(latest_connector) if latest_connector else None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    )


@bp.get("/api/opportunities")
def api_opportunities():
    opportunities = Opportunity.query.order_by(Opportunity.updated_at.desc()).all()
    return jsonify([serialize_opportunity(item) for item in opportunities])


@bp.get("/api/connectors")
def api_connectors():
    return jsonify(list_connectors(get_effective_config(current_app.config)))


@bp.post("/api/connectors/<connector_id>/run")
def api_run_connector(connector_id):
    result = run_connector(
        connector_id,
        get_effective_config(current_app.config),
        classifier=build_classifier(),
        provider=get_effective_config(current_app.config)["AI_PROVIDER"],
        model=get_effective_config(current_app.config)["OLLAMA_MODEL"],
    )
    db.session.commit()
    return jsonify(result.__dict__), 200 if result.status != "not_found" else 404


@bp.get("/api/workers")
def api_workers():
    return jsonify(list_worker_status())


@bp.post("/api/workers/<worker_id>/start")
def api_start_worker(worker_id):
    result = start_worker(worker_id)
    return jsonify(result), 200 if result["status"] != "not_found" else 404


@bp.post("/api/workers/<worker_id>/stop")
def api_stop_worker(worker_id):
    result = stop_worker(worker_id)
    return jsonify(result), 200 if result["status"] != "not_found" else 404


def build_classifier():
    values = get_effective_config(current_app.config)
    return get_classifier(
        values["AI_PROVIDER"],
        values["OLLAMA_URL"],
        values["OLLAMA_MODEL"],
    )


def serialize_opportunity(item):
    return {
        "id": item.id,
        "kind": item.kind,
        "title": item.title,
        "organization": item.organization,
        "status": item.status,
        "source": item.source,
        "deadline": item.deadline.isoformat() if item.deadline else None,
        "notes": item.notes,
        "updated_at": item.updated_at.isoformat(),
    }


def serialize_reminder(item):
    return {
        "id": item.id,
        "title": item.title,
        "due_at": item.due_at.isoformat(),
        "channel": item.channel,
        "is_done": item.is_done,
        "is_read": item.is_read,
        "notified_at": item.notified_at.isoformat() if item.notified_at else None,
        "opportunity_id": item.opportunity_id,
    }


def serialize_activity(item):
    return {
        "id": item.id,
        "source": item.source,
        "app_name": item.app_name,
        "category": item.category,
        "planned_task": item.planned_task,
        "actual_task": item.actual_task,
        "duration_minutes": item.duration_minutes,
        "agent_summary": item.agent_summary,
        "created_at": item.created_at.isoformat(),
    }


def serialize_inbox_item(item):
    return {
        "id": item.id,
        "sender": item.sender,
        "subject": item.subject,
        "category": item.category,
        "confidence": item.confidence,
        "created_at": item.created_at.isoformat(),
    }


def serialize_connector_run(item):
    return {
        "id": item.id,
        "connector_id": item.connector_id,
        "status": item.status,
        "message": item.message,
        "records_seen": item.records_seen,
        "records_imported": item.records_imported,
        "created_at": item.created_at.isoformat(),
    }


def build_dashboard_stats(opportunities, reminders, inbox_items, activity_events):
    active_reminders = [item for item in reminders if not item.is_done]
    avg_confidence = 0
    if inbox_items:
        avg_confidence = round(sum(item.confidence for item in inbox_items) / len(inbox_items) * 100)

    category_counts = {}
    for item in opportunities:
        category_counts[item.kind] = category_counts.get(item.kind, 0) + 1

    max_category = max(category_counts.values(), default=1)
    opportunity_graph = [
        {
            "label": label.title(),
            "count": count,
            "percent": max(8, round(count / max_category * 100)),
        }
        for label, count in sorted(category_counts.items())
    ]

    wellbeing_minutes = sum(item.duration_minutes for item in activity_events)
    wellbeing_graph = [
        {
            "label": item.app_name or item.category.title(),
            "minutes": item.duration_minutes,
            "percent": max(6, min(100, item.duration_minutes * 2)),
        }
        for item in activity_events
    ]

    return {
        "opportunities": len(opportunities),
        "active_reminders": len(active_reminders),
        "avg_confidence": avg_confidence,
        "wellbeing_minutes": wellbeing_minutes,
        "opportunity_graph": opportunity_graph,
        "wellbeing_graph": wellbeing_graph,
    }
