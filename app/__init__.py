import os
import secrets
from pathlib import Path

from flask import Flask
from sqlalchemy import text

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

    with app.app_context():
        if str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).startswith("sqlite"):
            with db.engine.connect() as connection:
                connection.exec_driver_sql("PRAGMA journal_mode=WAL")
                connection.exec_driver_sql("PRAGMA busy_timeout=30000")
        db.create_all()
        apply_lightweight_migrations()
        ensure_memory_user(app.config.get("USER_DISPLAY_NAME", "Local User"))

    return app


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
    inspector = db.inspect(db.engine)
    if "reminder" not in inspector.get_table_names():
        return

    migrations = []
    reminder_columns = {column["name"] for column in inspector.get_columns("reminder")}

    if "is_read" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN is_read BOOLEAN NOT NULL DEFAULT 0")
    if "notified_at" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN notified_at DATETIME")
    if "notification_type" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN notification_type VARCHAR(60) NOT NULL DEFAULT 'reminder'")
    if "priority" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN priority VARCHAR(40) NOT NULL DEFAULT 'normal'")
    if "source_key" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN source_key VARCHAR(240)")
    if "snoozed_until" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN snoozed_until DATETIME")
    if "metadata_json" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN metadata_json TEXT")

    if "setting" in inspector.get_table_names():
        setting_columns = {column["name"] for column in inspector.get_columns("setting")}
        if "updated_at" not in setting_columns:
            migrations.append("ALTER TABLE setting ADD COLUMN updated_at DATETIME")

    if "email_insight" in inspector.get_table_names():
        email_insight_columns = {column["name"] for column in inspector.get_columns("email_insight")}
        if "life_item_id" not in email_insight_columns:
            migrations.append("ALTER TABLE email_insight ADD COLUMN life_item_id INTEGER")
        if "required_documents_json" not in email_insight_columns:
            migrations.append("ALTER TABLE email_insight ADD COLUMN required_documents_json TEXT")
        if "repositories_json" not in email_insight_columns:
            migrations.append("ALTER TABLE email_insight ADD COLUMN repositories_json TEXT")
        if "suggested_actions_json" not in email_insight_columns:
            migrations.append("ALTER TABLE email_insight ADD COLUMN suggested_actions_json TEXT")

    for statement in migrations:
        db.session.execute(text(statement))

    if migrations:
        db.session.commit()


def ensure_memory_user(name):
    from app.services.memory_engine import ensure_user_entity

    ensure_user_entity(name)
    db.session.commit()
