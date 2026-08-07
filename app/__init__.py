import os
import secrets

from flask import Flask, current_app, jsonify, render_template, request
from sqlalchemy import event

from config import Config
from app.models import db
from app.routes import bp


def create_app(config_class=Config):
    instance_path = os.getenv("AIOS_INSTANCE_PATH", "").strip()
    app = Flask(__name__, instance_path=instance_path or None)
    app.config.from_object(config_class)
    configure_secret_key(app)

    db.init_app(app)
    app.register_blueprint(bp)
    register_error_pages(app)

    with app.app_context():
        if str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).startswith("sqlite"):
            @event.listens_for(db.engine, "connect")
            def _configure_sqlite_connection(connection, _record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

            with db.engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA journal_mode=WAL")
                connection.exec_driver_sql("PRAGMA busy_timeout=30000")
        db.create_all()
        apply_lightweight_migrations()
        ensure_memory_user(app.config.get("USER_DISPLAY_NAME", "Local User"))

    return app


def register_error_pages(app):
    def render_error(status_code, error_code, title, explanation, suggested_fix):
        if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
            return jsonify(
                {
                    "ok": False,
                    "error": error_code,
                    "message": explanation,
                    "suggested_fix": suggested_fix,
                }
            ), status_code
        return (
            render_template(
                "error.html",
                status_code=status_code,
                title=title,
                explanation=explanation,
                suggested_fix=suggested_fix,
                technical_details=f"HTTP {status_code} | {request.method} {request.path}",
            ),
            status_code,
        )

    app.register_error_handler(
        400,
        lambda _error: render_error(
            400,
            "bad_request",
            "AiOS could not understand that request",
            "The action was incomplete or contained a value AiOS could not use.",
            "Go back, review the form, and try once more.",
        ),
    )
    app.register_error_handler(
        403,
        lambda _error: render_error(
            403,
            "forbidden",
            "AiOS kept this action private",
            "This local session could not verify permission for the requested action.",
            "Return to the previous screen and retry from inside the AiOS app.",
        ),
    )
    app.register_error_handler(
        404,
        lambda _error: render_error(
            404,
            "not_found",
            "This page is not here",
            "The link may be outdated, or the page may have moved.",
            "Return to the dashboard or go back to the last working screen.",
        ),
    )
    app.register_error_handler(
        405,
        lambda _error: render_error(
            405,
            "method_not_allowed",
            "That action is not available here",
            "The current screen used an unsupported action for this address.",
            "Go back to the previous screen and use its available controls.",
        ),
    )
    app.register_error_handler(
        429,
        lambda _error: render_error(
            429,
            "too_many_requests",
            "AiOS needs a short pause",
            "Too many attempts arrived in a short period, so the local guard paused this action.",
            "Wait a moment, then retry once.",
        ),
    )
    app.register_error_handler(
        500,
        lambda _error: render_error(
            500,
            "internal_error",
            "AiOS could not finish that",
            "Your local data is still on this device, but this screen failed to load.",
            "Try again once. If it repeats, copy the error details and report the issue.",
        ),
    )


def configure_secret_key(app):
    configured = str(app.config.get("SECRET_KEY") or "").strip()
    if configured and configured not in {"change-me", "dev-secret"}:
        return

    secret_path = Path(app.instance_path) / "secret_key"
    secret_path.parent.mkdir(parents=True, exist_ok=True)

    if secret_path.exists():
        app.config["SECRET_KEY"] = secret_path.read_text(encoding="utf-8").strip()
        return

    generated = secrets.token_urlsafe(48)
    secret_path.write_text(generated, encoding="utf-8")
    try:
        os.chmod(secret_path, 0o600)
    except OSError:
        pass
    app.config["SECRET_KEY"] = generated


def apply_lightweight_migrations():
    from app.services.migrations import apply_migrations

    return apply_migrations(db.session, db.engine, current_app.logger)


def backup_sqlite_database():
    from app.services.migrations import create_sqlite_backup

    return create_sqlite_backup(db.engine.url.database)


def ensure_memory_user(name):
    from app.services.memory_engine import ensure_user_entity

    ensure_user_entity(name)
    db.session.commit()
