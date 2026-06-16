import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS browser_plan (
    id TEXT PRIMARY KEY,
    request TEXT NOT NULL,
    intent TEXT NOT NULL,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    approval_hash TEXT,
    created_at TEXT NOT NULL,
    executed_at TEXT
);
CREATE TABLE IF NOT EXISTS browser_action (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES browser_plan(id),
    sequence INTEGER NOT NULL,
    operation TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    started_at TEXT,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS job_opportunity (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    description TEXT,
    skills_json TEXT NOT NULL,
    match_score INTEGER NOT NULL,
    score_reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'saved',
    discovered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_url)
);
CREATE TABLE IF NOT EXISTS job_application (
    id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL REFERENCES job_opportunity(id),
    status TEXT NOT NULL,
    resume_version TEXT,
    cover_letter TEXT,
    answers_json TEXT NOT NULL,
    applied_at TEXT,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_browser_action_plan ON browser_action(plan_id, sequence);
CREATE INDEX IF NOT EXISTS idx_job_opportunity_score ON job_opportunity(match_score DESC);
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class BrowserAgentStore:
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
                INSERT INTO browser_plan
                (id, request, intent, status, risk_level, approval_hash, created_at)
                VALUES (?, ?, ?, 'planned', ?, ?, ?)
                """,
                (plan["id"], plan["request"], plan["intent"], plan["risk_level"], approval_hash, utc_now()),
            )
            for sequence, action in enumerate(plan["actions"], start=1):
                connection.execute(
                    """
                    INSERT INTO browser_action
                    (id, plan_id, sequence, operation, arguments_json, risk_level, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'planned')
                    """,
                    (
                        action["id"],
                        plan["id"],
                        sequence,
                        action["operation"],
                        json.dumps(action["arguments"]),
                        action["risk_level"],
                    ),
                )

    def get_plan(self, plan_id):
        with self.connect() as connection:
            plan = connection.execute("SELECT * FROM browser_plan WHERE id = ?", (plan_id,)).fetchone()
            if plan is None:
                return None
            actions = connection.execute(
                "SELECT * FROM browser_action WHERE plan_id = ? ORDER BY sequence", (plan_id,)
            ).fetchall()
        payload = dict(plan)
        payload.pop("approval_hash", None)
        payload["actions"] = []
        for row in actions:
            action = dict(row)
            action["arguments"] = json.loads(action.pop("arguments_json"))
            action["result"] = json.loads(action.pop("result_json") or "{}")
            payload["actions"].append(action)
        return payload

    def list_plans(self, limit=12):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id FROM browser_plan ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self.get_plan(row["id"]) for row in rows]

    def set_plan_status(self, plan_id, status):
        finished = utc_now() if status in {"completed", "failed", "awaiting_approval", "partial"} else None
        with self.connect() as connection:
            connection.execute(
                "UPDATE browser_plan SET status = ?, executed_at = COALESCE(?, executed_at) WHERE id = ?",
                (status, finished, plan_id),
            )

    def start_action(self, action_id):
        with self.connect() as connection:
            connection.execute(
                "UPDATE browser_action SET status = 'running', started_at = ? WHERE id = ?",
                (utc_now(), action_id),
            )

    def finish_action(self, action_id, status, result=None, error=None):
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE browser_action SET status = ?, result_json = ?, error = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, json.dumps(result or {}), error, utc_now(), action_id),
            )

    def save_opportunity(self, opportunity):
        opportunity_id = opportunity.get("id") or secrets.token_hex(12)
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_opportunity
                (id, source, source_url, title, company, location, description, skills_json,
                 match_score, score_reason, status, discovered_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET
                    title=excluded.title, company=excluded.company, location=excluded.location,
                    description=excluded.description, skills_json=excluded.skills_json,
                    match_score=excluded.match_score, score_reason=excluded.score_reason,
                    updated_at=excluded.updated_at
                """,
                (
                    opportunity_id,
                    opportunity["source"],
                    opportunity["source_url"],
                    opportunity["title"],
                    opportunity["company"],
                    opportunity.get("location", ""),
                    opportunity.get("description", ""),
                    json.dumps(opportunity.get("skills", [])),
                    int(opportunity.get("match_score", 0)),
                    opportunity.get("score_reason", ""),
                    opportunity.get("status", "saved"),
                    now,
                    now,
                ),
            )
        return opportunity_id

    def list_opportunities(self, limit=100):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_opportunity ORDER BY match_score DESC, discovered_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["skills"] = json.loads(item.pop("skills_json"))
            items.append(item)
        return items

    def update_application(self, opportunity_id, status, resume_version="", cover_letter="", answers=None):
        application_id = secrets.token_hex(12)
        now = utc_now()
        applied_at = now if status == "applied" else None
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM job_application WHERE opportunity_id = ?", (opportunity_id,)
            ).fetchone()
            if existing:
                application_id = existing["id"]
                connection.execute(
                    """
                    UPDATE job_application SET status=?, resume_version=?, cover_letter=?,
                    answers_json=?, applied_at=COALESCE(?, applied_at), updated_at=? WHERE id=?
                    """,
                    (status, resume_version, cover_letter, json.dumps(answers or {}), applied_at, now, application_id),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO job_application
                    (id, opportunity_id, status, resume_version, cover_letter, answers_json, applied_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (application_id, opportunity_id, status, resume_version, cover_letter, json.dumps(answers or {}), applied_at, now),
                )
            connection.execute(
                "UPDATE job_opportunity SET status=?, updated_at=? WHERE id=?",
                (status, now, opportunity_id),
            )
        return application_id
