import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS automation_plan (
    id TEXT PRIMARY KEY,
    request TEXT NOT NULL,
    intent TEXT NOT NULL,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    approval_hash TEXT,
    created_at TEXT NOT NULL,
    executed_at TEXT
);
CREATE TABLE IF NOT EXISTS automation_action (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES automation_plan(id),
    sequence INTEGER NOT NULL,
    tool TEXT NOT NULL,
    operation TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_automation_action_plan
ON automation_action(plan_id, sequence);
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class AutomationStore:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create_plan(self, plan, approval_hash):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO automation_plan
                (id, request, intent, status, risk_level, approval_hash, created_at)
                VALUES (?, ?, ?, 'planned', ?, ?, ?)
                """,
                (
                    plan["id"],
                    plan["request"],
                    plan["intent"],
                    plan["risk_level"],
                    approval_hash,
                    utc_now(),
                ),
            )
            for index, action in enumerate(plan["actions"], start=1):
                connection.execute(
                    """
                    INSERT INTO automation_action
                    (id, plan_id, sequence, tool, operation, arguments_json, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'planned')
                    """,
                    (
                        action["id"],
                        plan["id"],
                        index,
                        action["tool"],
                        action["operation"],
                        json.dumps(action["arguments"]),
                    ),
                )

    def get_plan(self, plan_id):
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM automation_plan WHERE id = ?", (plan_id,)
            ).fetchone()
            if row is None:
                return None
            actions = connection.execute(
                "SELECT * FROM automation_action WHERE plan_id = ? ORDER BY sequence",
                (plan_id,),
            ).fetchall()
        return self._serialize_plan(row, actions)

    def list_plans(self, limit=12):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id FROM automation_plan ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get_plan(row["id"]) for row in rows]

    def set_plan_status(self, plan_id, status):
        executed_at = utc_now() if status in {"completed", "failed", "partial"} else None
        with self.connect() as connection:
            connection.execute(
                "UPDATE automation_plan SET status = ?, executed_at = COALESCE(?, executed_at) WHERE id = ?",
                (status, executed_at, plan_id),
            )

    def start_action(self, action_id):
        with self.connect() as connection:
            connection.execute(
                "UPDATE automation_action SET status = 'running', started_at = ? WHERE id = ?",
                (utc_now(), action_id),
            )

    def finish_action(self, action_id, status, result=None, error=None):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE automation_action
                SET status = ?, result_json = ?, error = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, json.dumps(result or {}), error, utc_now(), action_id),
            )

    @staticmethod
    def _serialize_plan(row, actions):
        payload = dict(row)
        payload.pop("approval_hash", None)
        payload["actions"] = []
        for action in actions:
            item = dict(action)
            item["arguments"] = json.loads(item.pop("arguments_json"))
            item["result"] = json.loads(item.pop("result_json") or "{}")
            payload["actions"].append(item)
        return payload


def generate_approval_token():
    return secrets.token_urlsafe(18)
