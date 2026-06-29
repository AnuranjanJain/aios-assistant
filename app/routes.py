from datetime import datetime
from pathlib import Path
from time import monotonic
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.utils import secure_filename

from app.models import (
    ActivityEvent,
    ConnectorRun,
    HackathonUpdate,
    InboxItem,
    Opportunity,
    PlacementUpdate,
    Reminder,
    db,
)
from app.services.agent_ingest import ingest_message as ingest_agent_message
from app.services.ai_classifier import get_classifier
from app.services.automation import automation_overview, get_automation_engine
from app.services.browser_automation import browser_agent_overview, get_browser_agent
from app.services.career import career_overview, get_career_engine
from app.services.api_auth import has_valid_api_token
from app.services.auth import clear_pin, has_pin, set_pin, verify_pin
from app.services.connectors import (
    connect_gmail,
    disconnect_gmail,
    gmail_oauth_status,
    list_connectors,
    run_connector,
)
from app.services.data_pipelines import SUPPORTED_IMPORTS, import_source_file
from app.services.daily_planner import build_daily_plan
from app.services.hackathons import ingest_hackathon_signal, serialize_hackathon
from app.services.goal_planner import (
    create_goal_plan,
    log_task_session,
    planner_overview,
    serialize_plan,
    serialize_task,
    update_task,
)
from app.services.memory_engine import (
    answer_memory_question,
    memory_graph,
    memory_overview,
    relate_entities,
    remember,
    save_checkpoint,
    search_memory,
    serialize_checkpoint,
    serialize_entity,
    serialize_fact,
    serialize_relation,
    upsert_entity,
)
from runtime_paths import get_runtime_paths
from app.services.placements import ingest_placement_signal, is_neopat_signal, serialize_placement
from app.services.settings import SETTING_KEYS, apply_settings, get_effective_config, get_setting, set_setting
from app.services.startup import (
    save_startup_settings,
    startup_overview,
)
from app.services.wellbeing import summarize_activity
from app.services.workers import list_worker_status, start_worker, stop_worker


bp = Blueprint("main", __name__)
TRUSTED_BROWSER_ORIGINS = {
    "http://127.0.0.1:5000",
    "http://localhost:5000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
}
LOGIN_ATTEMPTS = {}
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW_SECONDS = 60


@bp.app_context_processor
def inject_desktop_shell_context():
    return {"desktop_profile": get_user_profile()}


def is_trusted_browser_origin(origin):
    return origin in TRUSTED_BROWSER_ORIGINS


def is_extension_origin(origin):
    return origin.startswith(("chrome-extension://", "moz-extension://"))


def safe_next_url(value):
    candidate = (value or "").strip()
    parsed = urlsplit(candidate)
    if candidate.startswith("/") and not candidate.startswith("//") and not parsed.netloc:
        return candidate
    return url_for("main.dashboard")


def recent_login_attempts(client_key):
    cutoff = monotonic() - LOGIN_ATTEMPT_WINDOW_SECONDS
    attempts = [attempt for attempt in LOGIN_ATTEMPTS.get(client_key, []) if attempt >= cutoff]
    LOGIN_ATTEMPTS[client_key] = attempts
    return attempts


@bp.before_app_request
def require_ui_auth():
    origin = request.headers.get("Origin", "")
    if origin and not is_trusted_browser_origin(origin):
        extension_preflight = request.method == "OPTIONS" and is_extension_origin(origin)
        extension_with_token = is_extension_origin(origin) and has_valid_api_token(request, current_app.config)
        if not extension_preflight and not extension_with_token:
            return jsonify({"error": "origin_not_allowed"}), 403

    if request.method == "OPTIONS":
        return None

    if not has_pin():
        return None

    if session.get("is_unlocked"):
        return None

    if request.endpoint in {"main.login", "main.unlock"}:
        return None

    if request.endpoint == "main.api_local_pairing" and not origin and request.remote_addr in {"127.0.0.1", "::1"}:
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
    origin = request.headers.get("Origin", "")
    allow_extension = is_extension_origin(origin) and (
        request.method == "OPTIONS" or has_valid_api_token(request, current_app.config)
    )
    if is_trusted_browser_origin(origin) or allow_extension:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-AiOS-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, OPTIONS"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@bp.get("/login")
def login():
    return render_template("login.html", has_pin=has_pin(), error="", next_url=request.args.get("next", ""))


@bp.post("/login")
def unlock():
    pin = request.form.get("pin", "")
    next_url = safe_next_url(request.form.get("next"))
    client_key = request.remote_addr or "local"

    if not has_pin():
        if not pin.isdigit() or not 4 <= len(pin) <= 12:
            return render_template(
                "login.html",
                has_pin=False,
                error="Use 4 to 12 digits.",
                next_url=next_url,
            ), 400
        set_pin(pin)
        db.session.commit()
        session.clear()
        session["is_unlocked"] = True
        return redirect(next_url)

    attempts = recent_login_attempts(client_key)
    if len(attempts) >= LOGIN_ATTEMPT_LIMIT:
        return render_template(
            "login.html",
            has_pin=True,
            error="Too many attempts. Wait one minute and try again.",
            next_url=next_url,
        ), 429

    if verify_pin(pin):
        LOGIN_ATTEMPTS.pop(client_key, None)
        session.clear()
        session["is_unlocked"] = True
        return redirect(next_url)

    attempts.append(monotonic())
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


@bp.get("/gmail")
def gmail_workspace():
    inbox_items = InboxItem.query.order_by(InboxItem.created_at.desc()).limit(80).all()
    runs = ConnectorRun.query.filter_by(connector_id="gmail").order_by(ConnectorRun.created_at.desc()).limit(12).all()
    return render_template(
        "pipeline.html",
        page_title="Gmail",
        page_kind="gmail",
        eyebrow="Gmail intelligence",
        heading="Messages turned into action.",
        description="Read-only Gmail signals, classified locally into hackathons, jobs, reminders, and follow-ups.",
        primary_action_url=url_for("main.connectors"),
        primary_action_label="Manage Gmail",
        items=inbox_items,
        runs=runs,
        activities=[],
    )


@bp.get("/hackathons")
def hackathons_workspace():
    items = Opportunity.query.filter_by(kind="hackathon").order_by(Opportunity.updated_at.desc()).all()
    runs = (
        ConnectorRun.query.filter(ConnectorRun.connector_id.in_(["gmail", "hackathon_platforms"]))
        .order_by(ConnectorRun.created_at.desc())
        .limit(12)
        .all()
    )
    return render_template(
        "pipeline.html",
        page_title="Hackathons",
        page_kind="hackathons",
        eyebrow="Hackathon corner",
        heading="Applied, open, live, and past events.",
        description="Track platforms, deadlines, result updates, and whether a hackathon is still only an opening or already applied.",
        primary_action_url=url_for("main.connectors"),
        primary_action_label="Scan Hackathons",
        items=items,
        runs=runs,
        activities=[],
    )


@bp.get("/jobs")
def jobs_workspace():
    items = [
        item
        for item in Opportunity.query.filter_by(kind="job").order_by(Opportunity.updated_at.desc()).all()
        if not is_neopat_opportunity(item)
    ]
    runs = (
        ConnectorRun.query.filter(ConnectorRun.connector_id.in_(["gmail", "job_portals"]))
        .order_by(ConnectorRun.created_at.desc())
        .limit(12)
        .all()
    )
    return render_template(
        "pipeline.html",
        page_title="Jobs",
        page_kind="jobs",
        eyebrow="Placement tracker",
        heading="Applications and company replies.",
        description="See applied roles, interview signals, assessments, rejections, offers, and unresolved openings.",
        primary_action_url=url_for("main.connectors"),
        primary_action_label="Scan Jobs",
        items=items,
        runs=runs,
        activities=[],
    )


@bp.get("/wellbeing")
def wellbeing_workspace():
    activities = ActivityEvent.query.order_by(ActivityEvent.created_at.desc()).limit(80).all()
    return render_template(
        "pipeline.html",
        page_title="Wellbeing",
        page_kind="wellbeing",
        eyebrow="Digital wellbeing",
        heading="Desktop activity and focus signals.",
        description="Activity captured from What Do You Do and the local desktop worker appears here for review.",
        primary_action_url=url_for("main.workers"),
        primary_action_label="Manage Worker",
        items=[],
        runs=[],
        activities=activities,
    )


@bp.get("/memory")
def memory_workspace():
    overview = memory_overview()
    return render_template("memory.html", **overview, graph=memory_graph())


@bp.get("/planner")
def planner_workspace():
    return render_template("planner.html", **planner_overview())


@bp.get("/automation")
def automation_workspace():
    return render_template(
        "automation.html",
        **automation_overview(),
        pending_plan=session.get("automation_pending_plan"),
    )


@bp.get("/browser-agent")
def browser_agent_workspace():
    return render_template(
        "browser_agent.html",
        **browser_agent_overview(),
        pending_plan=session.get("browser_pending_plan"),
    )


@bp.get("/career")
def career_workspace():
    return render_template("career.html", **career_overview())


@bp.post("/career/github/analyze")
def analyze_career_repository():
    try:
        get_career_engine().analyze_repository(
            request.form.get("source", ""),
            request.form.get("project_name", ""),
        )
    except ValueError as exc:
        return render_template("career.html", **career_overview(), error=str(exc)), 400
    return redirect(url_for("main.career_workspace"))


@bp.post("/career/resume/optimize")
def optimize_career_resume():
    try:
        result = get_career_engine().optimize_resume(
            request.form.get("resume_text", ""),
            request.form.get("job_description", ""),
        )
    except ValueError as exc:
        return render_template("career.html", **career_overview(), error=str(exc)), 400
    return render_template("career.html", **career_overview(), resume_result=result)


@bp.post("/career/jobs/match")
def match_career_job():
    try:
        result = get_career_engine().match_job(
            request.form.get("job_description", ""),
            request.form.get("title", ""),
            request.form.get("company", ""),
        )
    except ValueError as exc:
        return render_template("career.html", **career_overview(), error=str(exc)), 400
    return render_template("career.html", **career_overview(), match_result=result)


@bp.post("/career/applications")
def save_career_application():
    get_career_engine().save_application(
        {
            "company": request.form.get("company", "").strip(),
            "role": request.form.get("role", "").strip(),
            "status": request.form.get("status", "saved").strip(),
            "source_url": request.form.get("source_url", "").strip(),
            "interview_date": request.form.get("interview_date", "").strip(),
            "offer_details": request.form.get("offer_details", "").strip(),
            "feedback": request.form.get("feedback", "").strip(),
        }
    )
    return redirect(url_for("main.career_workspace"))


@bp.get("/api/career")
def api_career_overview():
    return jsonify(career_overview())


@bp.post("/browser-agent/plan")
def create_browser_plan():
    try:
        plan = get_browser_agent().create_plan(
            request.form.get("request", ""),
            {
                "source": request.form.get("source", "").strip() or None,
                "query": request.form.get("query", "").strip() or None,
                "location": request.form.get("location", "").strip(),
                "url": request.form.get("url", "").strip() or None,
                "max_results": request.form.get("max_results", "25"),
                "resume_version": request.form.get("resume_version", "").strip(),
                "cover_letter": request.form.get("cover_letter", "").strip(),
            },
        )
        session["browser_tokens"] = {
            **session.get("browser_tokens", {}),
            plan["id"]: plan.pop("approval_token"),
        }
        session["browser_pending_plan"] = plan
    except (TypeError, ValueError) as exc:
        return render_template(
            "browser_agent.html",
            **browser_agent_overview(),
            pending_plan=None,
            error=str(exc),
        ), 400
    return redirect(url_for("main.browser_agent_workspace"))


@bp.post("/browser-agent/plans/<plan_id>/execute")
def execute_browser_plan(plan_id):
    tokens = session.get("browser_tokens", {})
    profile = {
        "skills": [
            item.strip()
            for item in request.form.get("skills", "").split(",")
            if item.strip()
        ],
        "projects": [
            item.strip()
            for item in request.form.get("projects", "").split(",")
            if item.strip()
        ],
        "resume_keywords": [
            item.strip()
            for item in request.form.get("resume_keywords", "").split(",")
            if item.strip()
        ],
        "experience_years": request.form.get("experience_years", "0"),
    }
    try:
        get_browser_agent().execute_plan(plan_id, tokens.get(plan_id, ""), profile)
        session["browser_pending_plan"] = None
        tokens.pop(plan_id, None)
        session["browser_tokens"] = tokens
    except (KeyError, PermissionError, ValueError) as exc:
        return render_template(
            "browser_agent.html",
            **browser_agent_overview(),
            pending_plan=session.get("browser_pending_plan"),
            error=str(exc),
        ), 400
    return redirect(url_for("main.browser_agent_workspace"))


@bp.post("/browser-agent/opportunities/<opportunity_id>/status")
def update_browser_opportunity(opportunity_id):
    allowed = {"saved", "applied", "interview", "assessment", "rejected", "offer"}
    status = request.form.get("status", "saved").lower()
    if status not in allowed:
        return redirect(url_for("main.browser_agent_workspace"))
    get_browser_agent().store.update_application(
        opportunity_id,
        status,
        request.form.get("resume_version", ""),
        request.form.get("cover_letter", ""),
    )
    return redirect(url_for("main.browser_agent_workspace"))


@bp.get("/api/browser-agent")
def api_browser_agent_overview():
    return jsonify(browser_agent_overview())


@bp.post("/automation/plan")
def create_automation_plan():
    try:
        plan = get_automation_engine().create_plan(
            request.form.get("request", ""),
            {
                "source": request.form.get("source", "").strip() or None,
                "destination": request.form.get("destination", "").strip() or None,
                "parent": request.form.get("parent", "").strip() or None,
                "names": [
                    item.strip()
                    for item in request.form.get("names", "").split(",")
                    if item.strip()
                ],
                "title": request.form.get("title", "").strip() or None,
                "notes": request.form.get("notes", "").strip() or None,
            },
        )
        session["automation_tokens"] = {
            **session.get("automation_tokens", {}),
            plan["id"]: plan.pop("approval_token"),
        }
        session["automation_pending_plan"] = plan
    except ValueError as exc:
        return render_template(
            "automation.html",
            **automation_overview(),
            pending_plan=None,
            error=str(exc),
        ), 400
    return redirect(url_for("main.automation_workspace"))


@bp.post("/automation/plans/<plan_id>/execute")
def execute_automation_plan(plan_id):
    tokens = session.get("automation_tokens", {})
    try:
        result = get_automation_engine().execute_plan(plan_id, tokens.get(plan_id, ""))
        session["automation_pending_plan"] = None
        tokens.pop(plan_id, None)
        session["automation_tokens"] = tokens
        session["automation_result"] = result["status"]
    except (KeyError, PermissionError, ValueError) as exc:
        return render_template(
            "automation.html",
            **automation_overview(),
            pending_plan=session.get("automation_pending_plan"),
            error=str(exc),
        ), 400
    return redirect(url_for("main.automation_workspace"))


@bp.post("/automation/actions/<action_id>/restore")
def restore_automation_action(action_id):
    try:
        get_automation_engine().restore_action(action_id)
    except (KeyError, ValueError) as exc:
        return render_template(
            "automation.html",
            **automation_overview(),
            pending_plan=None,
            error=str(exc),
        ), 400
    return redirect(url_for("main.automation_workspace"))


@bp.get("/api/automation")
def api_automation_overview():
    return jsonify(automation_overview())


@bp.post("/planner")
def create_planner_goal():
    try:
        create_goal_plan(request.form, get_effective_config(current_app.config))
        db.session.commit()
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return render_template("planner.html", **planner_overview(), error=str(exc)), 400
    return redirect(url_for("main.planner_workspace"))


@bp.post("/planner/tasks/<int:task_id>")
def update_planner_task(task_id):
    try:
        update_task(task_id, request.form, get_effective_config(current_app.config))
        db.session.commit()
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return render_template("planner.html", **planner_overview(), error=str(exc)), 400
    return redirect(url_for("main.planner_workspace"))


@bp.post("/planner/tasks/<int:task_id>/sessions")
def create_planner_session(task_id):
    try:
        log_task_session(task_id, request.form, get_effective_config(current_app.config))
        db.session.commit()
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return render_template("planner.html", **planner_overview(), error=str(exc)), 400
    return redirect(url_for("main.planner_workspace"))


@bp.post("/memory/entity")
def create_memory_entity():
    try:
        upsert_entity(request.form)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return render_template("memory.html", **memory_overview(), graph=memory_graph(), error=str(exc)), 400
    return redirect(url_for("main.memory_workspace"))


@bp.post("/memory/checkpoint")
def create_memory_checkpoint():
    try:
        save_checkpoint(request.form, get_effective_config(current_app.config))
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return render_template("memory.html", **memory_overview(), graph=memory_graph(), error=str(exc)), 400
    return redirect(url_for("main.memory_workspace"))


@bp.get("/sources")
def sources():
    return render_template("sources.html", result=None)


@bp.get("/connectors")
def connectors():
    values = get_effective_config(current_app.config)
    runs = ConnectorRun.query.order_by(ConnectorRun.created_at.desc()).limit(12).all()
    result = runs[0] if request.args.get("last_run") and runs else None
    return render_template(
        "connectors.html",
        connectors=list_connectors(values),
        google=gmail_oauth_status(values, include_profile=True),
        runs=runs,
        result=result,
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
    return redirect(url_for("main.connectors", last_run=connector_id))


@bp.post("/connectors/google/connect")
def connect_google_route():
    try:
        connect_gmail(get_effective_config(current_app.config))
    except Exception as exc:
        return redirect(url_for("main.connectors", oauth_error=str(exc)))
    return redirect(url_for("main.connectors", google="connected"))


@bp.post("/connectors/google/disconnect")
def disconnect_google_route():
    disconnect_gmail(get_effective_config(current_app.config))
    return redirect(url_for("main.connectors", google="disconnected"))


@bp.get("/connectors/<connector_id>/run")
def connector_run_get_redirect(connector_id):
    return redirect(url_for("main.connectors"))


@bp.get("/settings")
def settings():
    values = get_effective_config(current_app.config)
    return render_template(
        "settings.html",
        keys=SETTING_KEYS,
        values=values,
        saved=False,
        pin_enabled=has_pin(),
        startup=startup_overview(),
        startup_result=None,
    )


@bp.get("/profile")
def profile():
    return render_template("profile.html", profile=get_user_profile(), saved=False)


@bp.post("/profile")
def save_profile():
    display_name = request.form.get("display_name", "").strip() or current_app.config.get("USER_DISPLAY_NAME", "Local User")
    role = request.form.get("role", "").strip()
    focus = request.form.get("focus", "").strip()
    set_setting("PROFILE_DISPLAY_NAME", display_name[:80])
    set_setting("PROFILE_ROLE", role[:100])
    set_setting("PROFILE_FOCUS", focus[:160])

    upload = request.files.get("profile_photo")
    if upload and upload.filename:
        suffix = Path(secure_filename(upload.filename)).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
            profile_dir = get_runtime_paths().data_dir / "profile"
            profile_dir.mkdir(parents=True, exist_ok=True)
            photo_path = profile_dir / f"avatar{suffix}"
            upload.save(photo_path)
            set_setting("PROFILE_PHOTO_PATH", str(photo_path))

    db.session.commit()
    return render_template("profile.html", profile=get_user_profile(), saved=True)


@bp.get("/profile/photo")
def profile_photo():
    photo_path = Path(get_setting("PROFILE_PHOTO_PATH", ""))
    if not photo_path.exists() or not photo_path.is_file():
        return redirect(url_for("static", filename="icons/aios-icon.svg"))
    return send_file(photo_path)


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
    settings_action = request.form.get("settings_action", "")
    pin_action = request.form.get("pin_action", "")
    new_pin = request.form.get("new_pin", "")
    startup_result = None

    if pin_action == "set_pin" and new_pin:
        set_pin(new_pin)
    elif pin_action == "clear_pin":
        clear_pin()

    if settings_action == "save_startup":
        startup_result = save_startup_settings(request.form)
    else:
        apply_settings(request.form)

    db.session.commit()
    values = get_effective_config(current_app.config)
    return render_template(
        "settings.html",
        keys=SETTING_KEYS,
        values=values,
        saved=True,
        pin_enabled=has_pin(),
        startup=startup_overview(),
        startup_result=startup_result,
    )


@bp.post("/sources/import")
def import_source():
    upload = request.files.get("source_file")
    if not upload or not upload.filename:
        return render_template("sources.html", result={"imported": 0, "filename": "No file selected."}), 400

    filename = secure_filename(upload.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_IMPORTS:
        return render_template("sources.html", result={"imported": 0, "filename": f"Unsupported file type: {suffix}"}), 400

    import_dir = Path(get_effective_config(current_app.config)["WATCH_IMPORT_DIR"]).parent / "manual"
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
        "profile": get_user_profile(),
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


@bp.get("/api/memory")
def api_memory_overview():
    return jsonify(memory_overview())


@bp.post("/api/memory/entities")
def api_create_memory_entity():
    try:
        entity = upsert_entity(request.get_json(silent=True) or {})
        db.session.commit()
        return jsonify(serialize_entity(entity, True)), 201
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.post("/api/memory/facts")
def api_create_memory_fact():
    try:
        fact = remember(request.get_json(silent=True) or {}, get_effective_config(current_app.config))
        db.session.commit()
        return jsonify(serialize_fact(fact)), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.post("/api/memory/checkpoints")
def api_create_memory_checkpoint():
    try:
        checkpoint = save_checkpoint(
            request.get_json(silent=True) or {},
            get_effective_config(current_app.config),
        )
        db.session.commit()
        return jsonify(
            {
                "project": serialize_entity(checkpoint.project, True),
                "checkpoint": serialize_checkpoint(checkpoint),
            }
        ), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.post("/api/memory/relations")
def api_create_memory_relation():
    try:
        relation = relate_entities(request.get_json(silent=True) or {})
        db.session.commit()
        return jsonify(serialize_relation(relation)), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.get("/api/memory/graph")
def api_memory_graph():
    return jsonify(memory_graph())


@bp.get("/api/memory/search")
def api_memory_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q is required"}), 400
    return jsonify(
        {
            "query": query,
            "results": search_memory(query, get_effective_config(current_app.config)),
        }
    )


@bp.post("/api/memory/ask")
def api_memory_ask():
    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    return jsonify(answer_memory_question(query, get_effective_config(current_app.config)))


@bp.get("/api/planner")
def api_planner_overview():
    return jsonify(planner_overview())


@bp.post("/api/planner")
def api_create_plan():
    try:
        plan = create_goal_plan(
            request.get_json(silent=True) or {},
            get_effective_config(current_app.config),
        )
        db.session.commit()
        return jsonify(serialize_plan(plan, include_tasks=True)), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.patch("/api/planner/tasks/<int:task_id>")
def api_update_plan_task(task_id):
    try:
        task = update_task(
            task_id,
            request.get_json(silent=True) or {},
            get_effective_config(current_app.config),
        )
        db.session.commit()
        return jsonify(serialize_task(task))
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.post("/api/planner/tasks/<int:task_id>/sessions")
def api_create_plan_session(task_id):
    try:
        session = log_task_session(
            task_id,
            request.get_json(silent=True) or {},
            get_effective_config(current_app.config),
        )
        db.session.commit()
        return jsonify({"session_id": session.id, "task": serialize_task(session.task)}), 201
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


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


@bp.get("/api/placements")
def api_placements():
    placements = [
        item
        for item in Opportunity.query.filter_by(kind="job").order_by(Opportunity.updated_at.desc()).all()
        if not is_neopat_opportunity(item)
    ]
    connector_runs = (
        ConnectorRun.query.filter(
            ConnectorRun.connector_id.in_(["gmail", "job_portals"])
        )
        .order_by(ConnectorRun.created_at.desc())
        .limit(8)
        .all()
    )
    return jsonify(
        {
            "placements": [serialize_placement(item) for item in placements],
            "connectors": [serialize_connector_run(item) for item in connector_runs],
            "unread_updates": sum(
                1
                for item in PlacementUpdate.query.join(Opportunity).filter(Opportunity.kind == "job").all()
                if not item.is_read and not is_neopat_opportunity(item.opportunity)
            ),
            "updated_at": datetime.utcnow().isoformat(),
        }
    )


@bp.get("/api/neopat")
def api_neopat():
    neopat_items = [
        item
        for item in Opportunity.query.order_by(Opportunity.updated_at.desc()).all()
        if item.kind == "neopat" or is_neopat_opportunity(item)
    ]
    connector_runs = (
        ConnectorRun.query.filter_by(connector_id="gmail")
        .order_by(ConnectorRun.created_at.desc())
        .limit(8)
        .all()
    )
    return jsonify(
        {
            "placements": [serialize_placement(item) for item in neopat_items],
            "connectors": [serialize_connector_run(item) for item in connector_runs],
            "unread_updates": sum(
                1
                for item in PlacementUpdate.query.join(Opportunity).all()
                if not item.is_read and (item.opportunity.kind == "neopat" or is_neopat_opportunity(item.opportunity))
            ),
            "updated_at": datetime.utcnow().isoformat(),
        }
    )


@bp.post("/api/placements/capture")
def api_capture_placement():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or data.get("subject") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    opportunity, update, created = ingest_placement_signal(
        title=title,
        source=(data.get("source") or "local api").strip(),
        body=(data.get("body") or data.get("content") or "").strip(),
        organization=(data.get("organization") or data.get("company") or "").strip(),
        status=(data.get("status") or "").strip(),
        kind=(data.get("kind") or "job").strip(),
        deadline=data.get("deadline"),
        external_id=(data.get("external_id") or "").strip(),
        occurred_at=data.get("occurred_at"),
    )
    db.session.commit()
    return jsonify(
        {
            "created": created,
            "placement": serialize_placement(opportunity),
            "update_id": update.id,
        }
    ), 201 if created else 200


@bp.post("/api/placements/refresh")
def api_refresh_placements():
    values = get_effective_config(current_app.config)
    results = []
    for connector_id in ("gmail", "job_portals"):
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


@bp.post("/api/placement-updates/<int:update_id>/read")
def api_mark_placement_update_read(update_id):
    update = PlacementUpdate.query.get_or_404(update_id)
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
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "activity_store_busy", "message": "AiOS is busy; retry this activity sync."}), 503

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


@bp.get("/api/desktop/status")
def api_desktop_status():
    paths = get_runtime_paths()
    return jsonify(
        {
            "desktop": bool(current_app.config.get("AIOS_DESKTOP")),
            "platform": __import__("sys").platform,
            "data_dir": str(paths.data_dir),
            "config_dir": str(paths.config_dir),
            "imports_dir": str(paths.imports_dir),
            "runtime_descriptor": str(paths.data_dir / "runtime.json"),
            "database": current_app.config.get("SQLALCHEMY_DATABASE_URI", ""),
            "ollama_url": get_effective_config(current_app.config)["OLLAMA_URL"],
        }
    )


@bp.get("/api/opportunities")
def api_opportunities():
    opportunities = Opportunity.query.order_by(Opportunity.updated_at.desc()).all()
    return jsonify([serialize_opportunity(item) for item in opportunities])


@bp.get("/api/connectors")
def api_connectors():
    return jsonify(list_connectors(get_effective_config(current_app.config)))


@bp.get("/api/local/pairing")
def api_local_pairing():
    if request.headers.get("Origin") or request.remote_addr not in {"127.0.0.1", "::1"}:
        return jsonify({"error": "loopback_only"}), 403
    token = get_effective_config(current_app.config)["LOCAL_API_TOKEN"]
    return jsonify(
        {
            "ok": bool(token),
            "service": "aios-assistant",
            "base_url": request.host_url.rstrip("/"),
            "api_token": token,
        }
    )


@bp.get("/api/oauth/google/status")
def api_google_status():
    return jsonify(gmail_oauth_status(get_effective_config(current_app.config), include_profile=True))


@bp.post("/api/oauth/google/connect")
def api_google_connect():
    try:
        return jsonify(connect_gmail(get_effective_config(current_app.config)))
    except Exception as exc:
        return jsonify({"connected": False, "message": str(exc)}), 400


@bp.post("/api/oauth/google/disconnect")
def api_google_disconnect():
    return jsonify(disconnect_gmail(get_effective_config(current_app.config)))


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


def get_user_profile():
    display_name = get_setting("PROFILE_DISPLAY_NAME", current_app.config.get("USER_DISPLAY_NAME", "Local User")).strip()
    role = get_setting("PROFILE_ROLE", "Local AI companion").strip() or "Local AI companion"
    focus = get_setting("PROFILE_FOCUS", "Build, track, and protect the local workflow.").strip()
    initials = "".join(part[:1] for part in display_name.split()[:2]).upper() or "A"
    return {
        "display_name": display_name,
        "role": role,
        "focus": focus,
        "initials": initials[:2],
        "photo_url": url_for("main.profile_photo"),
    }


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


def is_neopat_opportunity(item):
    return is_neopat_signal(item.title, item.organization, item.source, item.notes)


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
