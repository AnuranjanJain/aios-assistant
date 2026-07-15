import secrets
import threading
import webbrowser
from datetime import datetime, timedelta, timezone


_JOBS = {}
_LOCK = threading.RLock()
_TERMINAL_STATES = {"succeeded", "failed", "cancelled", "timed_out"}
_JOB_TTL = timedelta(minutes=15)


def _now():
    return datetime.now(timezone.utc)


def _purge_jobs():
    cutoff = _now() - _JOB_TTL
    expired = [job_id for job_id, job in _JOBS.items() if job["created_at"] < cutoff]
    for job_id in expired:
        _JOBS.pop(job_id, None)


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


def get_google_sign_in(job_id):
    with _LOCK:
        _purge_jobs()
        return _public_job(_JOBS.get(job_id))


def _set_authorization_url(job_id, authorization_url):
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job or job["status"] == "cancelled":
            return
        job.update(
            status="waiting",
            message="Finish choosing your Google account in the browser.",
            authorization_url=authorization_url,
            updated_at=_now(),
        )


def _is_cancelled(job_id):
    with _LOCK:
        job = _JOBS.get(job_id)
        return not job or job["status"] == "cancelled"


def _finish_job(job_id, result):
    with _LOCK:
        job = _JOBS.get(job_id)
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


def start_google_sign_in(flask_app, app_config, label="", connector=None):
    job_id = secrets.token_urlsafe(18)
    now = _now()
    with _LOCK:
        _purge_jobs()
        _JOBS[job_id] = {
            "id": job_id,
            "status": "starting",
            "message": "Preparing secure Google sign-in...",
            "authorization_url": "",
            "result": None,
            "created_at": now,
            "updated_at": now,
        }

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
                    on_authorization=lambda url: _set_authorization_url(job_id, url),
                    should_cancel=lambda: _is_cancelled(job_id),
                )
        except Exception:
            flask_app.logger.exception("Google sign-in job failed")
            result = {
                "ok": False,
                "status": "failed",
                "message": "Google sign-in could not finish. Return to Settings and try again.",
            }
        _finish_job(job_id, result)

    threading.Thread(target=run, name=f"google-sign-in-{job_id[:8]}", daemon=True).start()
    return get_google_sign_in(job_id)


def continue_google_sign_in(job_id):
    with _LOCK:
        job = _JOBS.get(job_id)
        authorization_url = job.get("authorization_url") if job else ""
        waiting = bool(job and job["status"] == "waiting")
    if not authorization_url or not waiting:
        return {"ok": False, "message": "The browser link is not ready. Please wait a moment."}
    opened = webbrowser.open(authorization_url, new=1, autoraise=True)
    return {
        "ok": bool(opened),
        "message": "Google sign-in opened in your browser." if opened else "AiOS could not open the browser. Check your default browser setting.",
    }


def cancel_google_sign_in(job_id):
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        if job["status"] not in _TERMINAL_STATES:
            job.update(
                status="cancelled",
                message="Sign-in cancelled. No Google account was added.",
                result={"ok": False, "message": "Google sign-in was cancelled."},
                updated_at=_now(),
            )
        return _public_job(job)


def consume_google_sign_in_result(job_id):
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        result = job.get("result") or {"ok": False, "message": job["message"]}
        if job["status"] in _TERMINAL_STATES:
            _JOBS.pop(job_id, None)
        return result
