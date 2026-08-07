"""Local data inventory, export, retention, and purge controls.

These operations intentionally stay inside the configured AiOS data directory.
Exports never contain OAuth bearer material, and purge uses explicit scopes so
the desktop can offer a useful privacy control without deleting the database
or application configuration by accident.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
import shutil

from app.models import db
from app.services.atomic_storage import atomic_write_text
from runtime_paths import get_runtime_paths


DEFAULT_RETENTION_DAYS = 365
MIN_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 3650
RETENTION_SETTING = "LOCAL_RETENTION_DAYS"

SECRET_NAME = re.compile(
    r"(token|secret|password|credential|authorization_url|result_json|api[_-]?key|client[_-]?secret)",
    re.I,
)
SENSITIVE_SETTING_NAME = re.compile(
    r"(token|secret|password|credential|api[_-]?key|client[_-]?secret|private[_-]?key)",
    re.I,
)

# Purge scopes are table names rather than model imports so this service stays
# compatible with future model additions and can compute child-first deletes.
PURGE_SCOPES = {
    "email": {
        "connected_account",
        "o_auth_token",
        "email_thread",
        "email_message",
        "email_attachment",
        "email_insight",
        "email_task",
        "inbox_item",
        "o_auth_sign_in_job",
    },
    "activity": {"activity_event"},
    "opportunities": {"hackathon_update", "placement_update", "reminder", "opportunity"},
    "memory": {
        "plan_task_session",
        "plan_task",
        "goal_plan",
        "work_checkpoint",
        "memory_fact",
        "memory_relation",
        "memory_entity",
        "project",
        "daily_plan",
        "weekly_plan",
        "daily_assistant_entry",
        "ai_suggestion",
    },
}


def _models_by_table():
    return {
        mapper.local_table.name: mapper.class_
        for mapper in db.Model.registry.mappers
    }


def _table_order(table_names):
    """Return a foreign-key child-first order for bulk deletes."""
    models = _models_by_table()
    remaining = {name for name in table_names if name in models}
    ordered = []
    while remaining:
        leaf = next(
            (
                name
                for name in remaining
                if not {
                    foreign_key.column.table.name
                    for foreign_key in models[name].__table__.foreign_keys
                }
                & remaining
            ),
            None,
        )
        if leaf is None:
            # A future cyclic relationship should still be deterministic. The
            # database will reject an unsafe delete instead of being disabled.
            leaf = sorted(remaining)[0]
        ordered.append(leaf)
        remaining.remove(leaf)
    return ordered


def _json_value(value):
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, bytes):
        return "[binary omitted]"
    return value


def _redact_column(model_name, column_name, value, row):
    if model_name in {"oauth_token", "o_auth_token"} or SECRET_NAME.search(column_name):
        return "[redacted]"
    setting_key = str(getattr(row, "key", ""))
    if model_name == "setting" and SENSITIVE_SETTING_NAME.search(setting_key):
        return "[redacted]"
    return _json_value(value)


def _rows_for_model(model):
    rows = []
    for row in db.session.query(model).all():
        values = {}
        for column in model.__table__.columns:
            values[column.name] = _redact_column(
                model.__tablename__,
                column.name,
                getattr(row, column.name),
                row,
            )
        rows.append(values)
    return rows


def _category_for_table(table_name):
    for category, tables in PURGE_SCOPES.items():
        if table_name in tables:
            return category
    return "configuration" if table_name == "setting" else "other"


def privacy_overview():
    paths = get_runtime_paths()
    models = _models_by_table()
    tables = []
    category_totals = {}
    for table_name, model in sorted(models.items()):
        count = db.session.query(model).count()
        category = _category_for_table(table_name)
        category_totals[category] = category_totals.get(category, 0) + count
        tables.append({"table": table_name, "category": category, "rows": count})

    database = paths.data_dir / "aios_assistant.db"
    retention = _retention_days()
    return {
        "ok": True,
        "retention_days": retention,
        "retention_enabled": retention > 0,
        "categories": category_totals,
        "tables": tables,
        "paths": {
            "data_dir": str(paths.data_dir),
            "database": str(database),
            "credentials": str(paths.credentials_dir),
            "exports": str(paths.data_dir / "exports"),
        },
        "exports": sorted(
            [path.name for path in (paths.data_dir / "exports").glob("aios-data-export-*.json")]
        )[-10:]
        if (paths.data_dir / "exports").exists()
        else [],
    }


def _retention_days():
    # Import lazily to avoid making model import order part of app startup.
    from app.models import Setting

    value = db.session.get(Setting, RETENTION_SETTING)
    if value is None or value.value in {None, ""}:
        return DEFAULT_RETENTION_DAYS
    try:
        parsed = int(value.value)
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    if parsed == 0:
        return 0
    return max(MIN_RETENTION_DAYS, min(MAX_RETENTION_DAYS, parsed))


def set_retention_days(value):
    parsed = int(value)
    if parsed != 0 and not MIN_RETENTION_DAYS <= parsed <= MAX_RETENTION_DAYS:
        raise ValueError(f"Retention must be 0 or between {MIN_RETENTION_DAYS} and {MAX_RETENTION_DAYS} days.")
    from app.models import Setting

    setting = db.session.get(Setting, RETENTION_SETTING)
    if setting is None:
        setting = Setting(key=RETENTION_SETTING)
        db.session.add(setting)
    setting.value = str(parsed)
    db.session.commit()
    return {"ok": True, "retention_days": parsed, "retention_enabled": parsed > 0}


def export_local_data():
    paths = get_runtime_paths()
    export_dir = paths.data_dir / "exports"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = export_dir / f"aios-data-export-{timestamp}.json"
    models = _models_by_table()
    payload = {
        "schema_version": 1,
        "exported_at": datetime.now().astimezone().isoformat(),
        "app": "AiOS Assistant",
        "privacy": "OAuth bearer material and local API/GitHub tokens are redacted.",
        "tables": {name: _rows_for_model(model) for name, model in sorted(models.items())},
    }
    atomic_write_text(target, json.dumps(payload, indent=2, ensure_ascii=True))
    return {
        "ok": True,
        "path": str(target),
        "filename": target.name,
        "bytes": target.stat().st_size,
        "tables": len(payload["tables"]),
        "rows": sum(len(rows) for rows in payload["tables"].values()),
    }


def purge_data(scope):
    scope = str(scope or "").strip().lower()
    models = _models_by_table()
    if scope == "everything":
        table_names = set(models) - {"setting"}
    elif scope in PURGE_SCOPES:
        table_names = PURGE_SCOPES[scope]
    else:
        raise ValueError("Choose email, activity, opportunities, memory, or everything.")

    deleted = {}
    try:
        for table_name in _table_order(table_names):
            model = models[table_name]
            deleted[table_name] = db.session.query(model).delete(synchronize_session=False)
        if scope == "everything":
            from app.models import Setting

            for setting in Setting.query.all():
                if SENSITIVE_SETTING_NAME.search(str(setting.key or "")):
                    setting.value = ""
            for key in ("PROFILE_DISPLAY_NAME", "PROFILE_ROLE", "PROFILE_FOCUS", "PROFILE_PHOTO_PATH"):
                setting = db.session.get(Setting, key)
                if setting is not None:
                    setting.value = ""
            for directory in (get_runtime_paths().data_dir / "profile", get_runtime_paths().data_dir / "exports"):
                if directory.exists() and directory.is_dir():
                    shutil.rmtree(directory)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {"ok": True, "scope": scope, "deleted": deleted, "total_deleted": sum(deleted.values())}


def apply_retention():
    """Trim operational history only; email and user content are retained."""
    days = _retention_days()
    if days <= 0:
        return {"ok": True, "retention_days": 0, "deleted": {}}
    cutoff = datetime.utcnow() - timedelta(days=days)
    from app.models import AgentDecision, ActivityEvent, ConnectorRun, OAuthSignInJob

    deleted = {
        "activity_event": db.session.query(ActivityEvent).filter(ActivityEvent.created_at < cutoff).delete(synchronize_session=False),
        "agent_decision": db.session.query(AgentDecision).filter(AgentDecision.created_at < cutoff).delete(synchronize_session=False),
        "connector_run": db.session.query(ConnectorRun).filter(ConnectorRun.created_at < cutoff).delete(synchronize_session=False),
        "oauth_sign_in_job": db.session.query(OAuthSignInJob).filter(OAuthSignInJob.updated_at < cutoff).delete(synchronize_session=False),
    }
    db.session.commit()
    return {"ok": True, "retention_days": days, "deleted": deleted, "total_deleted": sum(deleted.values())}
