import json
import subprocess
from datetime import datetime
from pathlib import Path

from app.models import GitHubRepository, LifeItem, db
from app.services.github_intelligence import parse_github_repo
from app.services.settings import get_setting, set_setting


def _json(value, fallback=None):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return [] if fallback is None else fallback


def project_context():
    selected_id = _selected_project_id()
    rows = (
        LifeItem.query.filter(
            (LifeItem.category == "project")
            | ((LifeItem.repository.isnot(None)) & (LifeItem.repository != ""))
            | ((LifeItem.working_directory.isnot(None)) & (LifeItem.working_directory != ""))
        )
        .order_by(LifeItem.updated_at.desc())
        .limit(300)
        .all()
    )
    grouped = {}
    for item in rows:
        repo_name = parse_github_repo(item.repository or "")
        key = f"repo:{repo_name.lower()}" if repo_name else f"item:{item.id}"
        grouped.setdefault(key, []).append(item)
    projects = [_serialize_project_group(items, selected_id) for items in grouped.values()]
    projects.sort(key=lambda item: (not item["selected"], -item["progress"], item["title"].lower()))
    return {
        "selected_project_id": selected_id,
        "selected": next((item for item in projects if item["selected"]), None),
        "projects": projects,
        "counts": {
            "total": len(projects),
            "with_repository": sum(bool(item["repository"]) for item in projects),
            "with_working_directory": sum(bool(item["working_directory"]) for item in projects),
        },
    }


def create_project(title, repository="", working_directory=""):
    cleaned_title = str(title or "").strip()
    if not cleaned_title:
        return {"ok": False, "message": "Project title is required."}
    repo_name = parse_github_repo(repository)
    source_key = f"github:{repo_name}" if repo_name else f"project:{cleaned_title.lower().replace(' ', '-')}"
    item = LifeItem.query.filter_by(source_key=source_key).first() or LifeItem(source_key=source_key)
    item.title = cleaned_title[:240]
    item.category = "project"
    item.status = "open"
    item.repository = _normalize_repository(repository)
    item.working_directory = _normalize_working_directory(working_directory)
    item.next_action = item.next_action or "Choose the next concrete task."
    db.session.add(item)
    db.session.flush()
    set_setting("ACTIVE_PROJECT_ID", str(item.id))
    _append_history(item, "project_created", "Project added to AiOS context.")
    db.session.commit()
    return {"ok": True, "project": serialize_project(item, item.id), "message": f"Tracking {item.title}."}


def update_project(project_id, payload):
    item = db.session.get(LifeItem, project_id)
    if item is None:
        return {"ok": False, "message": "Project not found."}
    if "repository" in payload:
        item.repository = _normalize_repository(payload.get("repository"))
    if "working_directory" in payload:
        item.working_directory = _normalize_working_directory(payload.get("working_directory"))
    if "progress" in payload:
        item.progress = max(0.0, min(100.0, float(payload.get("progress") or 0)))
    if "status" in payload:
        item.status = str(payload.get("status") or "open")[:40]
    if "next_action" in payload:
        item.next_action = str(payload.get("next_action") or "")[:2000]
    if payload.get("selected") is True or str(payload.get("selected", "")).lower() in {"1", "true", "yes", "on"}:
        set_setting("ACTIVE_PROJECT_ID", str(item.id))
    _append_history(item, "project_context_updated", str(payload.get("progress_note") or "Project context updated."))
    db.session.commit()
    return {"ok": True, "project": serialize_project(item, _selected_project_id()), "message": f"Updated {item.title}."}


def serialize_project(item, selected_id=None):
    return _serialize_project_group([item], selected_id)


def _serialize_project_group(items, selected_id=None):
    selected_item = next((item for item in items if item.id == selected_id), None)
    item = selected_item or max(
        items,
        key=lambda row: (
            row.category == "project",
            bool(row.working_directory),
            bool(row.next_action),
            row.updated_at or datetime.min,
        ),
    )
    repository = _repository_for_group(items)
    repository_url = next((row.repository for row in items if row.repository), "") or (repository.html_url if repository else "")
    working_directory = next((row.working_directory for row in items if row.working_directory), "")
    local_git = _local_git_snapshot(working_directory, repository_url)
    timeline = _project_timeline(items, repository, local_git)
    remote_progress = round(float(repository.completion_percentage or 0)) if repository else 0
    item_progress = max(round(float(row.progress or 0)) for row in items)
    progress = max(item_progress, remote_progress, (local_git or {}).get("progress", 0))
    remote_work = repository.recent_progress if repository else ""
    work_done = remote_work if remote_work and not remote_work.startswith("Repo linked;") else (local_git or {}).get("work_done", "")
    remaining_work = (repository.remaining_work if repository else "") or (local_git or {}).get("remaining_work", "")
    next_action = next((row.next_action for row in items if row.next_action and row.next_action != "Choose the next concrete task."), "")
    next_action = next_action or (repository.suggested_next_task if repository else "") or item.next_action
    if next_action == "Choose the next concrete task." and local_git:
        next_action = local_git["next_action"]
    title = item.title
    if len(items) > 1 and repository:
        title = repository.repo_full_name.rsplit("/", 1)[-1]
    return {
        "id": item.id,
        "title": title,
        "category": item.category,
        "status": item.status,
        "progress": progress,
        "deadline": item.deadline.isoformat() if item.deadline else None,
        "repository": repository_url,
        "working_directory": working_directory,
        "selected": selected_item is not None,
        "grouped_updates": len(items),
        "work_done": work_done or item.ai_summary or "",
        "remaining_work": remaining_work,
        "next_action": next_action,
        "inactive": bool(repository.inactive) if repository else False,
        "last_synced_at": repository.last_synced_at.isoformat() if repository and repository.last_synced_at else None,
        "timeline": timeline[:20],
    }


def _repository_for(item):
    row = GitHubRepository.query.filter_by(life_item_id=item.id).first()
    if row:
        return row
    repo_name = parse_github_repo(item.repository or "")
    return GitHubRepository.query.filter_by(repo_full_name=repo_name).first() if repo_name else None


def _repository_for_group(items):
    for item in items:
        repository = _repository_for(item)
        if repository:
            return repository
    return None


def _project_timeline(items, repository, local_git=None):
    if not isinstance(items, (list, tuple)):
        items = [items]
    entries = []
    for item in items:
        for event in _json(item.history_json):
            kind = event.get("event", "history")
            title = event.get("note") or kind.replace("_", " ").title()
            if kind == "email_insight_updated" and not event.get("note"):
                continue
            entries.append({"at": event.get("at"), "kind": kind, "title": title})
    if repository:
        for commit in _json(repository.commits_json)[:10]:
            title = commit.get("message", "Commit")
            if not str(title).lower().startswith("merge pull request"):
                entries.append({"at": commit.get("date"), "kind": "commit", "title": title, "url": commit.get("url", "")})
        for issue in _json(repository.issues_json)[:8]:
            entries.append({"at": issue.get("updated_at"), "kind": "issue", "title": f"Issue #{issue.get('number')}: {issue.get('title', '')}", "url": issue.get("url", "")})
        for pull in _json(repository.pull_requests_json)[:8]:
            entries.append({"at": pull.get("updated_at"), "kind": "pull_request", "title": f"PR #{pull.get('number')}: {pull.get('title', '')}", "url": pull.get("url", "")})
        for release in _json(repository.releases_json)[:5]:
            entries.append({"at": release.get("published_at"), "kind": "release", "title": f"Release: {release.get('name', '')}", "url": release.get("url", "")})
    remote_commit_titles = {entry["title"] for entry in entries if entry.get("kind") == "commit"}
    for commit in (local_git or {}).get("commits", []):
        if not commit["title"].lower().startswith("merge pull request") and commit["title"] not in remote_commit_titles:
            entries.append(commit)
    deduplicated = []
    seen = set()
    for entry in entries:
        key = (entry.get("kind"), str(entry.get("title", "")).strip().lower(), entry.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(entry)
    deduplicated.sort(key=lambda entry: entry.get("at") or "", reverse=True)
    return deduplicated


def _local_git_snapshot(working_directory, repository_url):
    path = Path(str(working_directory or "").strip())
    if not path.is_dir() or not (path / ".git").exists():
        return None

    def git(*args):
        result = subprocess.run(
            ["git", *args],
            cwd=path,
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            text=True,
            timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    try:
        branch = git("branch", "--show-current") or "detached HEAD"
        status_lines = [line for line in git("status", "--porcelain").splitlines() if line]
        commit_count = int(git("rev-list", "--count", "HEAD") or 0)
        commits = []
        base_url = _normalize_repository(repository_url)
        for line in git("log", "-10", "--pretty=format:%H%x1f%cI%x1f%s").splitlines():
            parts = line.split("\x1f", 2)
            if len(parts) != 3:
                continue
            sha, committed_at, title = parts
            commits.append(
                {
                    "at": committed_at,
                    "kind": "commit",
                    "title": title[:240],
                    "url": f"{base_url}/commit/{sha}" if base_url else "",
                }
            )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None

    recent_titles = [commit["title"] for commit in commits[:3]]
    work_done = "Recent local commits: " + " | ".join(recent_titles) if recent_titles else "Local Git repository linked."
    if status_lines:
        remaining_work = f"{len(status_lines)} uncommitted file change{'s' if len(status_lines) != 1 else ''} need review on {branch}."
        next_action = f"Review and commit the {len(status_lines)} local change{'s' if len(status_lines) != 1 else ''}."
    else:
        remaining_work = ""
        next_action = f"Continue from the latest {branch} commit."
    return {
        "branch": branch,
        "commits": commits,
        "progress": min(40, max(5, commit_count * 8)) if commit_count else 0,
        "work_done": work_done,
        "remaining_work": remaining_work,
        "next_action": next_action,
    }


def _selected_project_id():
    try:
        return int(get_setting("ACTIVE_PROJECT_ID", "0") or 0)
    except ValueError:
        return 0


def _normalize_repository(value):
    repo_name = parse_github_repo(str(value or "").strip())
    return f"https://github.com/{repo_name}" if repo_name else ""


def _normalize_working_directory(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    path = Path(raw).expanduser()
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _append_history(item, event, note):
    history = _json(item.history_json)
    history.append({"at": datetime.utcnow().isoformat(), "event": event, "note": note[:500]})
    item.history_json = json.dumps(history[-50:], ensure_ascii=True)
