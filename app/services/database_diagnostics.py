"""Safe, copy-only diagnostics for a local SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def diagnose_sqlite_copy(database: str | Path, destination: str | Path) -> dict[str, object]:
    """Copy a database before checking its structural integrity.

    The report intentionally contains no rows, schema SQL, credentials, or
    message content. It is suitable for deciding whether an offline recovery
    workflow needs to operate on a verified backup.
    """

    source = Path(database).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite database was not found: {source}")

    target_directory = Path(destination).expanduser().resolve()
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{source.name}.diagnostic-copy"
    if target.exists():
        raise FileExistsError(f"Diagnostic copy already exists: {target}")

    source_connection = sqlite3.connect(source, timeout=30)
    copy_connection = sqlite3.connect(target, timeout=30)
    try:
        source_connection.backup(copy_connection)
        integrity = copy_connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = copy_connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()[0]
    finally:
        copy_connection.close()
        source_connection.close()

    return {
        "ok": integrity == "ok",
        "source_path": str(source),
        "copy_path": str(target),
        "integrity": integrity,
        "table_count": int(tables),
    }
