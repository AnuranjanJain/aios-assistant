"""Restore an AiOS SQLite backup after stopping all AiOS processes.

This is intentionally an explicit command. It creates a safety backup of the
current database before restoring the selected migration backup.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.migrations import restore_sqlite_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore an AiOS SQLite migration backup")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--yes", action="store_true", help="confirm the offline restore")
    args = parser.parse_args()
    if not args.yes:
        parser.error("refusing to restore without --yes")
    try:
        safety_backup = restore_sqlite_backup(args.database, args.backup)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "database": str(args.database.resolve()),
                "restored_from": str(args.backup.resolve()),
                "safety_backup": str(safety_backup),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
