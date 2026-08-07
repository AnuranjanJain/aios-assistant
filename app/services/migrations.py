"""Small, explicit SQLite migration ledger for the local AiOS database.

The app keeps migrations deliberately boring: each step adds only a nullable
or defaulted column, records a checksum, and creates one consistent backup
before the first schema change. Rollback is an explicit offline operation so
the running app never silently replaces a user's database.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import inspect, text


LOGGER = logging.getLogger(__name__)
LEDGER_TABLE = "aios_schema_migration"


@dataclass(frozen=True)
class ColumnAddition:
    table: str
    column: str
    statement: str


@dataclass(frozen=True)
class MigrationSpec:
    version: str
    additions: tuple[ColumnAddition, ...]

    @property
    def checksum(self) -> str:
        payload = self.version + "\n" + "\n".join(
            f"{item.table}.{item.column}:{item.statement}" for item in self.additions
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


MIGRATIONS: tuple[MigrationSpec, ...] = (
    MigrationSpec(
        "2026-08-08-reminder-state-v1",
        (
            ColumnAddition("reminder", "is_read", "ALTER TABLE reminder ADD COLUMN is_read BOOLEAN NOT NULL DEFAULT 0"),
            ColumnAddition("reminder", "notified_at", "ALTER TABLE reminder ADD COLUMN notified_at DATETIME"),
            ColumnAddition("reminder", "notification_type", "ALTER TABLE reminder ADD COLUMN notification_type VARCHAR(60) NOT NULL DEFAULT 'reminder'"),
            ColumnAddition("reminder", "priority", "ALTER TABLE reminder ADD COLUMN priority VARCHAR(40) NOT NULL DEFAULT 'normal'"),
            ColumnAddition("reminder", "source_key", "ALTER TABLE reminder ADD COLUMN source_key VARCHAR(240)"),
            ColumnAddition("reminder", "snoozed_until", "ALTER TABLE reminder ADD COLUMN snoozed_until DATETIME"),
            ColumnAddition("reminder", "metadata_json", "ALTER TABLE reminder ADD COLUMN metadata_json TEXT"),
        ),
    ),
    MigrationSpec(
        "2026-08-08-email-intelligence-v1",
        (
            ColumnAddition("email_insight", "life_item_id", "ALTER TABLE email_insight ADD COLUMN life_item_id INTEGER"),
            ColumnAddition("email_insight", "required_documents_json", "ALTER TABLE email_insight ADD COLUMN required_documents_json TEXT"),
            ColumnAddition("email_insight", "repositories_json", "ALTER TABLE email_insight ADD COLUMN repositories_json TEXT"),
            ColumnAddition("email_insight", "suggested_actions_json", "ALTER TABLE email_insight ADD COLUMN suggested_actions_json TEXT"),
            ColumnAddition("email_insight", "attention_score", "ALTER TABLE email_insight ADD COLUMN attention_score INTEGER NOT NULL DEFAULT 0"),
            ColumnAddition("email_insight", "priority_reason", "ALTER TABLE email_insight ADD COLUMN priority_reason TEXT"),
            ColumnAddition("email_insight", "is_actionable", "ALTER TABLE email_insight ADD COLUMN is_actionable BOOLEAN NOT NULL DEFAULT 0"),
        ),
    ),
    MigrationSpec(
        "2026-08-08-opportunity-links-v1",
        (
            ColumnAddition("opportunity", "source_key", "ALTER TABLE opportunity ADD COLUMN source_key VARCHAR(240)"),
            ColumnAddition("opportunity", "email_message_id", "ALTER TABLE opportunity ADD COLUMN email_message_id INTEGER"),
        ),
    ),
    MigrationSpec(
        "2026-08-08-inbox-intelligence-v1",
        (
            ColumnAddition("inbox_item", "source_key", "ALTER TABLE inbox_item ADD COLUMN source_key VARCHAR(240)"),
            ColumnAddition("inbox_item", "email_message_id", "ALTER TABLE inbox_item ADD COLUMN email_message_id INTEGER"),
            ColumnAddition("inbox_item", "summary", "ALTER TABLE inbox_item ADD COLUMN summary TEXT"),
            ColumnAddition("inbox_item", "next_action", "ALTER TABLE inbox_item ADD COLUMN next_action TEXT"),
            ColumnAddition("inbox_item", "occurred_at", "ALTER TABLE inbox_item ADD COLUMN occurred_at DATETIME"),
            ColumnAddition("inbox_item", "priority", "ALTER TABLE inbox_item ADD COLUMN priority VARCHAR(40) NOT NULL DEFAULT 'normal'"),
            ColumnAddition("inbox_item", "urgency", "ALTER TABLE inbox_item ADD COLUMN urgency VARCHAR(40) NOT NULL DEFAULT 'normal'"),
            ColumnAddition("inbox_item", "attention_score", "ALTER TABLE inbox_item ADD COLUMN attention_score INTEGER NOT NULL DEFAULT 0"),
            ColumnAddition("inbox_item", "priority_reason", "ALTER TABLE inbox_item ADD COLUMN priority_reason TEXT"),
            ColumnAddition("inbox_item", "is_actionable", "ALTER TABLE inbox_item ADD COLUMN is_actionable BOOLEAN NOT NULL DEFAULT 0"),
            ColumnAddition("inbox_item", "is_unread", "ALTER TABLE inbox_item ADD COLUMN is_unread BOOLEAN NOT NULL DEFAULT 0"),
            ColumnAddition("inbox_item", "account_email", "ALTER TABLE inbox_item ADD COLUMN account_email VARCHAR(240)"),
        ),
    ),
    MigrationSpec(
        "2026-08-08-settings-and-projects-v1",
        (
            ColumnAddition("setting", "updated_at", "ALTER TABLE setting ADD COLUMN updated_at DATETIME"),
            ColumnAddition("life_item", "working_directory", "ALTER TABLE life_item ADD COLUMN working_directory VARCHAR(1000)"),
        ),
    ),
    MigrationSpec(
        "2026-08-08-notification-claims-v1",
        (
            ColumnAddition("reminder", "notification_claim_id", "ALTER TABLE reminder ADD COLUMN notification_claim_id VARCHAR(80)"),
            ColumnAddition("reminder", "notification_claimed_until", "ALTER TABLE reminder ADD COLUMN notification_claimed_until DATETIME"),
        ),
    ),
    MigrationSpec(
        "2026-08-08-mail-time-normalization-v1",
        (
            ColumnAddition(
                "connected_account",
                "mail_time_version",
                "ALTER TABLE connected_account ADD COLUMN mail_time_version INTEGER NOT NULL DEFAULT 0",
            ),
        ),
    ),
)


def _database_path(database: str | Path | None) -> Path | None:
    if not database or str(database) == ":memory:":
        return None
    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def create_sqlite_backup(database: str | Path | None) -> Path | None:
    """Create a consistent, mode-600 backup of a SQLite database."""
    source = _database_path(database)
    if source is None or not source.exists():
        return None
    backup_dir = source.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_dir / f"{source.name}.{stamp}.bak"
    suffix = 1
    while backup.exists():
        backup = backup_dir / f"{source.name}.{stamp}.{suffix}.bak"
        suffix += 1
    temporary = backup.with_name(f".{backup.name}.tmp")
    source_connection = sqlite3.connect(str(source), timeout=30)
    backup_connection = sqlite3.connect(str(temporary), timeout=30)
    try:
        source_connection.backup(backup_connection)
        backup_connection.commit()
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        backup_connection.close()
        source_connection.close()
    os.replace(temporary, backup)
    try:
        os.chmod(backup, 0o600)
    except OSError:
        pass
    return backup


def restore_sqlite_backup(database: str | Path, backup: str | Path) -> Path:
    """Restore a backup into a database path, returning the safety backup."""
    target = _database_path(database)
    source = _database_path(backup)
    if target is None or source is None or not source.exists():
        raise ValueError("A file-backed database and an existing backup are required.")
    if target == source:
        raise ValueError("The rollback source and target must be different files.")
    safety_backup = create_sqlite_backup(target)
    source_connection = sqlite3.connect(str(source), timeout=30)
    target_connection = sqlite3.connect(str(target), timeout=30)
    try:
        source_connection.backup(target_connection)
        target_connection.commit()
    finally:
        target_connection.close()
        source_connection.close()
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return safety_backup or target


def _ensure_ledger(session, engine) -> None:
    session.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {LEDGER_TABLE} "
            "(version VARCHAR(100) PRIMARY KEY, applied_at DATETIME NOT NULL, "
            "checksum VARCHAR(64) NOT NULL DEFAULT '', backup_path VARCHAR(1000))"
        )
    )
    raw_connection = engine.raw_connection()
    try:
        columns = {
            column[1]
            for column in raw_connection.execute(f"PRAGMA table_info({LEDGER_TABLE})")
        }
    finally:
        raw_connection.close()
    if "checksum" not in columns:
        session.execute(text(f"ALTER TABLE {LEDGER_TABLE} ADD COLUMN checksum VARCHAR(64) NOT NULL DEFAULT ''"))
    if "backup_path" not in columns:
        session.execute(text(f"ALTER TABLE {LEDGER_TABLE} ADD COLUMN backup_path VARCHAR(1000)"))
    session.commit()


def _missing_additions(engine, spec: MigrationSpec) -> list[ColumnAddition]:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    columns = {table: {item["name"] for item in inspector.get_columns(table)} for table in tables}
    return [
        addition
        for addition in spec.additions
        if addition.table in tables and addition.column not in columns[addition.table]
    ]


def apply_migrations(session, engine, logger: logging.Logger | None = None) -> list[str]:
    """Apply pending named migrations and return their versions.

    Existing ``legacy-lightweight-v1`` rows are preserved as historical data;
    the named steps are adopted idempotently on the next startup.
    """
    logger = logger or LOGGER
    _ensure_ledger(session, engine)
    applied_rows = session.execute(
        text(f"SELECT version, checksum FROM {LEDGER_TABLE}")
    ).all()
    known_specs = {spec.version: spec for spec in MIGRATIONS}
    applied = {row[0] for row in applied_rows}
    for version, checksum in applied_rows:
        spec = known_specs.get(version)
        if spec and checksum and checksum != spec.checksum:
            raise RuntimeError(
                f"Migration checksum mismatch for {version}; refusing to continue."
            )
    pending = [spec for spec in MIGRATIONS if spec.version not in applied]
    if not pending:
        return []

    backup_path: Path | None = None
    applied_versions: list[str] = []
    try:
        for spec in pending:
            missing = _missing_additions(engine, spec)
            if missing and backup_path is None:
                backup_path = create_sqlite_backup(engine.url.database)
                if backup_path:
                    logger.info("Created SQLite migration backup at %s", backup_path)
            for addition in missing:
                session.execute(text(addition.statement))
            session.execute(
                text(
                    f"INSERT INTO {LEDGER_TABLE}(version, applied_at, checksum, backup_path) "
                    "VALUES (:version, CURRENT_TIMESTAMP, :checksum, :backup_path)"
                ),
                {
                    "version": spec.version,
                    "checksum": spec.checksum,
                    "backup_path": str(backup_path) if backup_path else None,
                },
            )
            session.commit()
            applied_versions.append(spec.version)
    except Exception:
        session.rollback()
        logger.exception("SQLite migration failed; restore the recorded backup before retrying if needed.")
        raise
    return applied_versions


def migration_status(session) -> list[dict[str, str | None]]:
    """Return the migration ledger without exposing database contents."""
    try:
        rows = session.execute(
            text(f"SELECT version, applied_at, checksum, backup_path FROM {LEDGER_TABLE} ORDER BY applied_at, version")
        ).mappings()
    except Exception:
        return []
    return [dict(row) for row in rows]
