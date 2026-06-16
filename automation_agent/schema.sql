-- Runtime schema is also embedded in automation_agent/store.py.
-- This file documents the portable automation audit database.
CREATE TABLE automation_plan (
    id TEXT PRIMARY KEY,
    request TEXT NOT NULL,
    intent TEXT NOT NULL,
    status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    approval_hash TEXT,
    created_at TEXT NOT NULL,
    executed_at TEXT
);

CREATE TABLE automation_action (
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
