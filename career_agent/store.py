import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS career_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT,
    headline TEXT,
    target_roles_json TEXT NOT NULL,
    skills_json TEXT NOT NULL,
    goals_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS github_repository (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT,
    local_path TEXT,
    languages_json TEXT NOT NULL,
    frameworks_json TEXT NOT NULL,
    technologies_json TEXT NOT NULL,
    architecture_json TEXT NOT NULL,
    complexity_json TEXT NOT NULL,
    documentation_json TEXT NOT NULL,
    commit_activity_json TEXT NOT NULL,
    score INTEGER NOT NULL,
    analyzed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_profile (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    repository_id TEXT,
    status TEXT NOT NULL,
    strengths_json TEXT NOT NULL,
    weaknesses_json TEXT NOT NULL,
    missing_components_json TEXT NOT NULL,
    relevance_json TEXT NOT NULL,
    portfolio_score INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_node (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    label TEXT NOT NULL,
    properties_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS graph_edge (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_id, target_id, relation)
);
CREATE TABLE IF NOT EXISTS resume_version (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    original_text TEXT NOT NULL,
    job_description TEXT,
    optimized_text TEXT NOT NULL,
    ats_score INTEGER NOT NULL,
    changes_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS job_match (
    id TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    job_description TEXT NOT NULL,
    skill_score INTEGER NOT NULL,
    technology_score INTEGER NOT NULL,
    experience_score INTEGER NOT NULL,
    project_score INTEGER NOT NULL,
    overall_score INTEGER NOT NULL,
    explanation TEXT NOT NULL,
    matched_skills_json TEXT NOT NULL,
    missing_skills_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS career_application (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    source_url TEXT,
    interview_date TEXT,
    offer_details TEXT,
    feedback TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS career_recommendation (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    priority INTEGER NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    action_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vector_document (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    text TEXT NOT NULL,
    terms_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_project_score ON project_profile(portfolio_score DESC);
CREATE INDEX IF NOT EXISTS idx_job_match_score ON job_match(overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_application_status ON career_application(status);
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class CareerStore:
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
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def upsert_profile(self, profile):
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO career_profile
                (id, name, headline, target_roles_json, skills_json, goals_json, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, headline=excluded.headline,
                    target_roles_json=excluded.target_roles_json,
                    skills_json=excluded.skills_json, goals_json=excluded.goals_json,
                    updated_at=excluded.updated_at
                """,
                (
                    profile.get("name", "Anuranjan"),
                    profile.get("headline", "AI systems builder"),
                    json.dumps(profile.get("target_roles", [])),
                    json.dumps(profile.get("skills", [])),
                    json.dumps(profile.get("goals", [])),
                    now,
                ),
            )

    def get_profile(self):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM career_profile WHERE id=1").fetchone()
        if row is None:
            return {
                "name": "Anuranjan",
                "headline": "AI systems builder",
                "target_roles": ["AI Engineer", "Backend Engineer", "Automation Engineer"],
                "skills": ["Python", "FastAPI", "SQLite", "LLM agents", "React"],
                "goals": ["Build AiOS", "Improve portfolio", "Track applications"],
            }
        return self._decode(dict(row), ("target_roles_json", "skills_json", "goals_json"))

    def save_repository(self, analysis):
        now = utc_now()
        repo_id = analysis.get("id") or secrets.token_hex(12)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO github_repository
                (id, name, source, source_url, local_path, languages_json, frameworks_json,
                 technologies_json, architecture_json, complexity_json, documentation_json,
                 commit_activity_json, score, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    languages_json=excluded.languages_json, frameworks_json=excluded.frameworks_json,
                    technologies_json=excluded.technologies_json, architecture_json=excluded.architecture_json,
                    complexity_json=excluded.complexity_json, documentation_json=excluded.documentation_json,
                    commit_activity_json=excluded.commit_activity_json, score=excluded.score,
                    analyzed_at=excluded.analyzed_at
                """,
                (
                    repo_id,
                    analysis["name"],
                    analysis["source"],
                    analysis.get("source_url", ""),
                    analysis.get("local_path", ""),
                    json.dumps(analysis["languages"]),
                    json.dumps(analysis["frameworks"]),
                    json.dumps(analysis["technologies"]),
                    json.dumps(analysis["architecture"]),
                    json.dumps(analysis["complexity"]),
                    json.dumps(analysis["documentation"]),
                    json.dumps(analysis["commit_activity"]),
                    int(analysis["score"]),
                    now,
                ),
            )
        analysis["id"] = repo_id
        return repo_id

    def list_repositories(self, limit=50):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM github_repository ORDER BY analyzed_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._decode(dict(row), (
            "languages_json", "frameworks_json", "technologies_json", "architecture_json",
            "complexity_json", "documentation_json", "commit_activity_json",
        )) for row in rows]

    def save_project(self, project):
        now = utc_now()
        project_id = project.get("id") or secrets.token_hex(12)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO project_profile
                (id, name, repository_id, status, strengths_json, weaknesses_json,
                 missing_components_json, relevance_json, portfolio_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    repository_id=excluded.repository_id, status=excluded.status,
                    strengths_json=excluded.strengths_json, weaknesses_json=excluded.weaknesses_json,
                    missing_components_json=excluded.missing_components_json,
                    relevance_json=excluded.relevance_json, portfolio_score=excluded.portfolio_score,
                    updated_at=excluded.updated_at
                """,
                (
                    project_id,
                    project["name"],
                    project.get("repository_id", ""),
                    project.get("status", "Active"),
                    json.dumps(project["strengths"]),
                    json.dumps(project["weaknesses"]),
                    json.dumps(project["missing_components"]),
                    json.dumps(project["relevance"]),
                    int(project["portfolio_score"]),
                    now,
                ),
            )
        project["id"] = project_id
        return project_id

    def list_projects(self, limit=50):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM project_profile ORDER BY portfolio_score DESC, updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._decode(dict(row), (
            "strengths_json", "weaknesses_json", "missing_components_json", "relevance_json",
        )) for row in rows]

    def upsert_graph_node(self, node_type, label, properties=None):
        node_id = f"{node_type}:{label}".lower().replace(" ", "-")
        now = utc_now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO graph_node (id, type, label, properties_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET properties_json=excluded.properties_json,
                updated_at=excluded.updated_at
                """,
                (node_id, node_type, label, json.dumps(properties or {}), now),
            )
        return node_id

    def upsert_graph_edge(self, source_id, target_id, relation, weight=1.0):
        now = utc_now()
        edge_id = secrets.token_hex(12)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO graph_edge (id, source_id, target_id, relation, weight, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, relation) DO UPDATE SET
                weight=excluded.weight, updated_at=excluded.updated_at
                """,
                (edge_id, source_id, target_id, relation, float(weight), now),
            )

    def graph(self):
        with self.connect() as connection:
            nodes = connection.execute("SELECT * FROM graph_node ORDER BY type, label").fetchall()
            edges = connection.execute("SELECT * FROM graph_edge ORDER BY relation").fetchall()
        return {
            "nodes": [self._decode(dict(row), ("properties_json",)) for row in nodes],
            "edges": [dict(row) for row in edges],
        }

    def save_resume(self, result):
        resume_id = result.get("id") or secrets.token_hex(12)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO resume_version
                (id, title, original_text, job_description, optimized_text, ats_score, changes_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resume_id,
                    result.get("title", "Optimized Resume"),
                    result["original_text"],
                    result.get("job_description", ""),
                    result["optimized_text"],
                    int(result["ats_score"]),
                    json.dumps(result["changes"]),
                    utc_now(),
                ),
            )
        result["id"] = resume_id
        return resume_id

    def save_job_match(self, result):
        match_id = result.get("id") or secrets.token_hex(12)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO job_match
                (id, title, company, job_description, skill_score, technology_score,
                 experience_score, project_score, overall_score, explanation,
                 matched_skills_json, missing_skills_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    result.get("title", ""),
                    result.get("company", ""),
                    result["job_description"],
                    int(result["skill_score"]),
                    int(result["technology_score"]),
                    int(result["experience_score"]),
                    int(result["project_score"]),
                    int(result["overall_score"]),
                    result["explanation"],
                    json.dumps(result["matched_skills"]),
                    json.dumps(result["missing_skills"]),
                    utc_now(),
                ),
            )
        result["id"] = match_id
        return match_id

    def list_job_matches(self, limit=20):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_match ORDER BY overall_score DESC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._decode(dict(row), ("matched_skills_json", "missing_skills_json")) for row in rows]

    def save_application(self, application):
        application_id = application.get("id") or secrets.token_hex(12)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO career_application
                (id, company, role, status, source_url, interview_date, offer_details, feedback, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    company=excluded.company, role=excluded.role, status=excluded.status,
                    source_url=excluded.source_url, interview_date=excluded.interview_date,
                    offer_details=excluded.offer_details, feedback=excluded.feedback,
                    updated_at=excluded.updated_at
                """,
                (
                    application_id,
                    application["company"],
                    application["role"],
                    application.get("status", "saved"),
                    application.get("source_url", ""),
                    application.get("interview_date", ""),
                    application.get("offer_details", ""),
                    application.get("feedback", ""),
                    utc_now(),
                ),
            )
        application["id"] = application_id
        return application_id

    def list_applications(self, limit=50):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM career_application ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def replace_recommendations(self, recommendations):
        now = utc_now()
        with self.connect() as connection:
            connection.execute("DELETE FROM career_recommendation")
            for item in recommendations:
                connection.execute(
                    """
                    INSERT INTO career_recommendation
                    (id, category, priority, title, rationale, action_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        secrets.token_hex(12),
                        item["category"],
                        int(item["priority"]),
                        item["title"],
                        item["rationale"],
                        json.dumps(item.get("action", {})),
                        now,
                    ),
                )

    def list_recommendations(self):
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM career_recommendation ORDER BY priority DESC, created_at DESC"
            ).fetchall()
        return [self._decode(dict(row), ("action_json",)) for row in rows]

    def save_vector_document(self, source_type, source_id, text, terms):
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO vector_document (id, source_type, source_id, text, terms_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET text=excluded.text, terms_json=excluded.terms_json,
                updated_at=excluded.updated_at
                """,
                (f"{source_type}:{source_id}", source_type, source_id, text, json.dumps(sorted(terms)), utc_now()),
            )

    def search_documents(self, terms, limit=10):
        terms = set(terms)
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM vector_document").fetchall()
        scored = []
        for row in rows:
            item = self._decode(dict(row), ("terms_json",))
            saved_terms = set(item["terms"])
            if not saved_terms:
                continue
            score = len(terms & saved_terms) / max(1, len(terms | saved_terms))
            if score:
                item["score"] = round(score, 3)
                scored.append(item)
        return sorted(scored, key=lambda item: item["score"], reverse=True)[:limit]

    def _decode(self, row, keys):
        for key in keys:
            value = json.loads(row.pop(key) or "[]")
            row[key.removesuffix("_json")] = value
        return row
