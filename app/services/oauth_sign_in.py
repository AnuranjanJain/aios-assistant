import json
import secrets
import threading
import webbrowser
from datetime import datetime, timedelta, timezone

from flask import current_app, has_app_context

from app.models import OAuthSignInJob, db


_JOBS = {}
_LOCK = threading.RLock()
_LAST_APP = None
_TERMINAL_STATES = {"succeeded", "failed", "cancelled", "timed_out"}
_JOB_TTL = timedelta(minutes=15)


def _now():
    return datetime.now(timezone.utc)


def _database_app(app=None):
    if app is not None:
        return app
    try:
        return current_app._get_current_object()
    except RuntimeError:
        return _LAST_APP


def _database_available(app):
    return app is not None and "sqlalchemy" in app.extensions


def _database_call(app, callback):
    if not _database_available(app):
        return None
    if has_app_context():
        return callback()
    with app.app_context():
        return callback()


def _naive_utc(value):
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _aware_utc(value):
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc)
    return value.replace(tzinfo=timezone.utc)


def _job_from_row(row):
    try:
        result = json.loads(row.result_json) if row.result_json else None
    except (TypeError, ValueError):
        result = None
    return {
        "id": row.id,
        "status": row.status,
        "message": row.message,
        "authorization_url": row.authorization_url or "",
        "result": result,
        "created_at": _aware_utc(row.created_at),
        "updated_at": _aware_utc(row.updated_at),
    }


def _persist_job(app, job):
    def save():
        row = db.session.get(OAuthSignInJob, job["id"])
        if row is None:
            row = OAuthSignInJob(id=job["id"])
            db.session.add(row)
        row.status = job["status"]
        row.message = job["message"]
        row.authorization_url = job.get("authorization_url") or ""
        row.result_json = json.dumps(job.get("result"), separators=(",", ":")) if job.get("result") is not None else None
        row.created_at = _naive_utc(job["created_at"])
        row.updated_at = _naive_utc(job["updated_at"])
        db.session.commit()

    try:
        _database_call(app, save)
    except Exception:
        if _database_available(app):
            try:
                db.session.rollback()
            except Exception:
                pass
        app.logger.exception("Could not persist Google sign-in job")


def _load_persisted_job(app, job_id):
    def load():
        row = db.session.get(OAuthSignInJob, job_id)
        return _job_from_row(row) if row else None

    try:
        return _database_call(app, load)
    except Exception:
        app.logger.exception("Could not load Google sign-in job")
        return None


def _delete_persisted_job(app, job_id):
    def remove():
        row = db.session.get(OAuthSignInJob, job_id)
        if row is not None:
            db.session.delete(row)
            db.session.commit()

    try:
        _database_call(app, remove)
    except Exception:
        if _database_available(app):
            try:
                db.session.rollback()
            except Exception:
                pass
        app.logger.exception("Could not remove Google sign-in job")


def _purge_jobs(app=None):
    cutoff = _now() - _JOB_TTL
    expired = [job_id for job_id, job in _JOBS.items() if job["created_at"] < cutoff]
    for job_id in expired:
        _JOBS.pop(job_id, None)

    app = _database_app(app)
    if not _database_available(app):
        return

    def purge():
        db.session.query(OAuthSignInJob).filter(
            OAuthSignInJob.created_at < _naive_utc(cutoff)
        ).delete(synchronize_session=False)
        db.session.commit()

    try:
        _database_call(app, purge)
    except Exception:
        db.session.rollback()
        app.logger.exception("Could not purge expired Google sign-in jobs")


def _get_job(job_id, app=None):
    app = _database_app(app)
    job = _JOBS.get(job_id)
    if job is not None:
        return job
    job = _load_persisted_job(app, job_id)
    if job is not None:
        if job["status"] in {"starting", "waiting"}:
            message = "AiOS restarted during Google sign-in. Start a new sign-in to resume safely."
            job.update(
                status="failed",
                message=message,
                result={"ok": False, "message": message},
                updated_at=_now(),
            )
            _persist_job(app, job)
        _JOBS[job_id] = job
    return job


def _public_job(job):
    if not job:
        return None
    return {
        "id": job["id"],
        "status": job["status"],
        "message": job["message"],
        "can_continue": bool(job.get("authorization_url")) and job["status"] == "waiting",
        "terminal": job["status"] in _TERMINAL_STATES,
        "created_at": job["created_at"].isoformat(),
        "updated_at": job["updated_at"].isoformat(),
    }


def get_google_sign_in(job_id, app=None):
    app = _database_app(app)
    with _LOCK:
        _purge_jobs(app)
        return _public_job(_get_job(job_id, app))


def _set_authorization_url(app, job_id, authorization_url):
    with _LOCK:
        job = _get_job(job_id, app)
        if not job or job["status"] == "cancelled":
            return
        job.update(
            status="waiting",
            message="Finish choosing your Google account in the browser.",
            authorization_url=authorization_url,
            updated_at=_now(),
        )
        _persist_job(app, job)


def _is_cancelled(app, job_id):
    with _LOCK:
        job = _get_job(job_id, app)
        return not job or job["status"] == "cancelled"


def _finish_job(app, job_id, result):
    with _LOCK:
        job = _get_job(job_id, app)
        if not job or job["status"] == "cancelled":
            return
        status = result.get("status") or ("succeeded" if result.get("ok") else "failed")
        if status not in _TERMINAL_STATES:
            status = "failed"
        message = result.get("message") or "Google sign-in finished."
        job.update(
            status=status,
            message=message,
            result={"ok": bool(result.get("ok")), "message": message},
            updated_at=_now(),
        )
        _persist_job(app, job)


def start_google_sign_in(flask_app, app_config, label="", connector=None):
    global _LAST_APP
    _LAST_APP = flask_app
    job_id = secrets.token_urlsafe(18)
    now = _now()
    job = {
        "id": job_id,
        "status": "starting",
        "message": "Preparing secure Google sign-in...",
        "authorization_url": "",
        "result": None,
        "created_at": now,
        "updated_at": now,
    }
    with _LOCK:
        _purge_jobs(flask_app)
        _JOBS[job_id] = job
        _persist_job(flask_app, job)

    def run():
        try:
            if connector is None:
                from app.services.email_intelligence import connect_google_account

                connect = connect_google_account
            else:
                connect = connector
            with flask_app.app_context():
                result = connect(
                    app_config,
                    label=label,
                    on_authorization=lambda url: _set_authorization_url(flask_app, job_id, url),
                    should_cancel=lambda: _is_cancelled(flask_app, job_id),
                )
        except Exception:
            flask_app.logger.exception("Google sign-in job failed")
            result = {
                "ok": False,
                "status": "failed",
                "message": "Google sign-in could not finish. Return to Settings and try again.",
            }
        _finish_job(flask_app, job_id, result)

    threading.Thread(target=run, name=f"google-sign-in-{job_id[:8]}", daemon=True).start()
    return get_google_sign_in(job_id, flask_app)


def continue_google_sign_in(job_id, app=None):
    app = _database_app(app)
    with _LOCK:
        job = _get_job(job_id, app)
        authorization_url = job.get("authorization_url") if job else ""
        waiting = bool(job and job["status"] == "waiting")
    if not authorization_url or not waiting:
        return {"ok": False, "message": "The browser link is not ready. Please wait a moment."}
    opened = webbrowser.open(authorization_url, new=1, autoraise=True)
    return {
        "ok": bool(opened),
        "message": "Google sign-in opened in your browser." if opened else "AiOS could not open the browser. Check your default browser setting.",
    }


def cancel_google_sign_in(job_id, app=None):
    app = _database_app(app)
    with _LOCK:
        job = _get_job(job_id, app)
        if not job:
            return None
        if job["status"] not in _TERMINAL_STATES:
            job.update(
                status="cancelled",
                message="Sign-in cancelled. No Google account was added.",
                result={"ok": False, "message": "Google sign-in was cancelled."},
                updated_at=_now(),
            )
            _persist_job(app, job)
        return _public_job(job)


def consume_google_sign_in_result(job_id, app=None):
    app = _database_app(app)
    with _LOCK:
        job = _get_job(job_id, app)
        if not job:
            return None
        result = job.get("result") or {"ok": False, "message": job["message"]}
        if job["status"] in _TERMINAL_STATES:
            _JOBS.pop(job_id, None)
            _delete_persisted_job(app, job_id)
        return result
