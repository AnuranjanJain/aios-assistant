import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from flask import current_app

from app.models import GitHubDailySummary, GitHubRepository, LifeItem, LifeItemRelation, PlanningEvent, db
from app.services.settings import get_effective_config


def _dump(value):
    return json.dumps(value or [], ensure_ascii=False)


def _dump_object(value):
    return json.dumps(value or {}, ensure_ascii=False)


def _json(value, fallback=None):
    if fallback is None:
        fallback = []
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def parse_github_repo(url):
    match = re.search(r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s.#?]+)", url or "", re.I)
    if not match:
        return ""
    return f"{match.group('owner')}/{match.group('repo').replace('.git', '')}"


def github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "aios-github-intelligence",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        token = get_effective_config(current_app.config).get("GITHUB_TOKEN", "").strip()
    except RuntimeError:
        token = ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_json(url, headers=None, timeout=4.0):
    request = urllib.request.Request(url, headers=headers or github_headers())
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def discover_repository_urls():
    urls = set()
    for event in PlanningEvent.query.filter(PlanningEvent.repo_url.isnot(None)).all():
        if parse_github_repo(event.repo_url):
            urls.add(event.repo_url)
    for item in LifeItem.query.filter(LifeItem.repository.isnot(None)).all():
        if parse_github_repo(item.repository):
            urls.add(item.repository)
    return sorted(urls)


def update_all_repositories(limit=30):
    results = []
    for repo_url in discover_repository_urls()[:limit]:
        results.append(update_repository(repo_url))
    daily = generate_daily_summary()
    db.session.commit()
    return {"ok": True, "repositories": results, "daily_summary": serialize_daily_summary(daily)}


def update_repository(repo_url):
    repo_full_name = parse_github_repo(repo_url)
    if not repo_full_name:
        return {"ok": False, "repo": repo_url, "message": "Not a GitHub repository URL."}

    row = GitHubRepository.query.filter_by(repo_full_name=repo_full_name).first()
    if row is None:
        row = GitHubRepository(repo_full_name=repo_full_name, html_url=f"https://github.com/{repo_full_name}")
        db.session.add(row)

    try:
        snapshot = fetch_repository_snapshot(repo_full_name)
        apply_repository_snapshot(row, snapshot)
        link_repository_to_life_item(row)
        refresh_planning_events(row)
        return {"ok": True, "repo": repo_full_name, "summary": serialize_repository(row)}
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError, KeyError) as exc:
        row.last_synced_at = datetime.utcnow()
        row.raw_json = _dump_object({"error": str(exc)})
        if not row.recent_progress:
            row.recent_progress = "Repo linked; latest GitHub intelligence not fetched yet."
        return {"ok": False, "repo": repo_full_name, "message": str(exc)}


def fetch_repository_snapshot(repo_full_name):
    headers = github_headers()
    encoded = urllib.parse.quote(repo_full_name, safe="/")
    repo = github_json(f"https://api.github.com/repos/{encoded}", headers)
    commits = github_json(f"https://api.github.com/repos/{encoded}/commits?per_page=10", headers)
    pulls = github_json(f"https://api.github.com/repos/{encoded}/pulls?state=all&per_page=10", headers)
    issues = github_json(f"https://api.github.com/repos/{encoded}/issues?state=all&per_page=20", headers)
    branches = github_json(f"https://api.github.com/repos/{encoded}/branches?per_page=20", headers)
    releases = github_json(f"https://api.github.com/repos/{encoded}/releases?per_page=10", headers)
    discussions = fetch_discussions(repo_full_name, headers)
    workflows = github_json(f"https://api.github.com/repos/{encoded}/actions/workflows?per_page=20", headers)
    contributors = github_json(f"https://api.github.com/repos/{encoded}/contributors?per_page=20", headers)
    return {
        "repo": repo,
        "commits": commits,
        "pulls": pulls,
        "issues": [item for item in issues if "pull_request" not in item],
        "branches": branches,
        "releases": releases,
        "discussions": discussions,
        "workflows": workflows.get("workflows", []) if isinstance(workflows, dict) else workflows,
        "contributors": contributors,
    }


def fetch_discussions(repo_full_name, headers):
    owner, repo = repo_full_name.split("/", 1)
    query = {
        "query": (
            "query($owner:String!,$repo:String!){repository(owner:$owner,name:$repo){"
            "discussions(first:10,orderBy:{field:UPDATED_AT,direction:DESC}){nodes{title,url,createdAt,updatedAt,answerChosenAt}}}}"
        ),
        "variables": {"owner": owner, "repo": repo},
    }
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(query).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=4.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return []
    nodes = payload.get("data", {}).get("repository", {}).get("discussions", {}).get("nodes", [])
    return nodes or []


def apply_repository_snapshot(row, snapshot):
    repo = snapshot["repo"]
    commits = normalize_commits(snapshot["commits"])
    pulls = normalize_items(snapshot["pulls"])
    issues = normalize_items(snapshot["issues"])
    branches = normalize_branches(snapshot["branches"])
    releases = normalize_releases(snapshot["releases"])
    discussions = normalize_discussions(snapshot["discussions"])
    workflows = normalize_workflows(snapshot["workflows"])
    contributors = normalize_contributors(snapshot["contributors"])

    row.html_url = repo.get("html_url") or row.html_url
    row.description = repo.get("description") or ""
    row.default_branch = repo.get("default_branch") or ""
    row.primary_language = repo.get("language") or ""
    row.is_private = bool(repo.get("private"))
    row.is_archived = bool(repo.get("archived"))
    row.pushed_at = parse_github_time(repo.get("pushed_at"))
    row.last_synced_at = datetime.utcnow()
    row.inactive = is_inactive(row.pushed_at, commits, issues, pulls)
    row.commits_json = _dump(commits)
    row.pull_requests_json = _dump(pulls)
    row.issues_json = _dump(issues)
    row.branches_json = _dump(branches)
    row.releases_json = _dump(releases)
    row.discussions_json = _dump(discussions)
    row.workflows_json = _dump(workflows)
    row.contributors_json = _dump(contributors)
    row.completion_percentage = estimate_completion(commits, pulls, issues, releases)
    row.current_sprint = summarize_current_sprint(pulls, issues, branches)
    row.remaining_work = summarize_remaining_work(issues, pulls, workflows)
    row.recent_progress = summarize_recent_progress(commits, pulls, releases)
    row.suggested_next_task = suggest_next_task(row, issues, pulls, workflows)
    row.raw_json = _dump_object(
        {
            "counts": {
                "commits": len(commits),
                "pull_requests": len(pulls),
                "issues": len(issues),
                "branches": len(branches),
                "releases": len(releases),
                "discussions": len(discussions),
                "workflows": len(workflows),
                "contributors": len(contributors),
            }
        }
    )


def normalize_commits(items):
    rows = []
    for item in items or []:
        commit = item.get("commit", {})
        rows.append(
            {
                "sha": (item.get("sha") or "")[:12],
                "message": (commit.get("message") or "").splitlines()[0][:240],
                "author": (commit.get("author") or {}).get("name") or "",
                "date": (commit.get("committer") or {}).get("date") or (commit.get("author") or {}).get("date") or "",
                "url": item.get("html_url") or "",
            }
        )
    return rows


def normalize_items(items):
    rows = []
    for item in items or []:
        rows.append(
            {
                "number": item.get("number"),
                "title": item.get("title") or "",
                "state": item.get("state") or "",
                "created_at": item.get("created_at") or "",
                "updated_at": item.get("updated_at") or "",
                "closed_at": item.get("closed_at") or "",
                "url": item.get("html_url") or "",
                "labels": [label.get("name") for label in item.get("labels", []) if label.get("name")],
                "draft": bool(item.get("draft")),
            }
        )
    return rows


def normalize_branches(items):
    return [{"name": item.get("name") or "", "protected": bool(item.get("protected"))} for item in items or []]


def normalize_releases(items):
    return [
        {
            "name": item.get("name") or item.get("tag_name") or "",
            "tag": item.get("tag_name") or "",
            "published_at": item.get("published_at") or "",
            "draft": bool(item.get("draft")),
            "prerelease": bool(item.get("prerelease")),
            "url": item.get("html_url") or "",
        }
        for item in items or []
    ]


def normalize_discussions(items):
    return [
        {
            "title": item.get("title") or "",
            "updated_at": item.get("updatedAt") or "",
            "answered": bool(item.get("answerChosenAt")),
            "url": item.get("url") or "",
        }
        for item in items or []
    ]


def normalize_workflows(items):
    return [
        {
            "name": item.get("name") or "",
            "state": item.get("state") or "",
            "path": item.get("path") or "",
            "url": item.get("html_url") or item.get("url") or "",
        }
        for item in items or []
    ]


def normalize_contributors(items):
    return [
        {
            "login": item.get("login") or "",
            "contributions": int(item.get("contributions") or 0),
            "url": item.get("html_url") or "",
        }
        for item in items or []
    ]


def parse_github_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def is_inactive(pushed_at, commits, issues, pulls):
    newest = pushed_at
    for item in commits + issues + pulls:
        candidate = parse_github_time(item.get("date") or item.get("updated_at") or item.get("closed_at"))
        if candidate and (newest is None or candidate > newest):
            newest = candidate
    if newest is None:
        return True
    return newest < datetime.utcnow() - timedelta(days=14)


def estimate_completion(commits, pulls, issues, releases):
    open_issues = sum(1 for item in issues if item.get("state") == "open")
    closed_issues = sum(1 for item in issues if item.get("state") == "closed")
    open_prs = sum(1 for item in pulls if item.get("state") == "open")
    merged_or_closed_prs = sum(1 for item in pulls if item.get("state") == "closed")
    completed = closed_issues + merged_or_closed_prs + len(releases)
    remaining = open_issues + open_prs
    if completed + remaining == 0:
        return min(40, len(commits) * 8)
    return max(5, min(100, round(100 * completed / (completed + remaining))))


def summarize_current_sprint(pulls, issues, branches):
    open_prs = [item["title"] for item in pulls if item.get("state") == "open"][:3]
    open_issues = [item["title"] for item in issues if item.get("state") == "open"][:3]
    active_branches = [item["name"] for item in branches if item.get("name") not in {"main", "master"}][:3]
    parts = []
    if open_prs:
        parts.append("PRs: " + "; ".join(open_prs))
    if open_issues:
        parts.append("Issues: " + "; ".join(open_issues))
    if active_branches:
        parts.append("Branches: " + ", ".join(active_branches))
    return ". ".join(parts) or "No active sprint signals found."


def summarize_remaining_work(issues, pulls, workflows):
    open_issues = [item["title"] for item in issues if item.get("state") == "open"][:4]
    open_prs = [item["title"] for item in pulls if item.get("state") == "open"][:4]
    disabled_workflows = [item["name"] for item in workflows if item.get("state") not in {"active", ""}][:2]
    parts = []
    if open_issues:
        parts.append("Open issues: " + "; ".join(open_issues))
    if open_prs:
        parts.append("Open PRs: " + "; ".join(open_prs))
    if disabled_workflows:
        parts.append("Workflow attention: " + "; ".join(disabled_workflows))
    return ". ".join(parts) or "No obvious remaining GitHub work."


def summarize_recent_progress(commits, pulls, releases):
    commit_titles = [f"{item.get('date', '')[:10]} {item.get('message', '')}" for item in commits[:3]]
    closed_prs = [item["title"] for item in pulls if item.get("state") == "closed"][:2]
    release_titles = [item["name"] for item in releases[:2]]
    parts = []
    if commit_titles:
        parts.append("Recent commits: " + " | ".join(commit_titles))
    if closed_prs:
        parts.append("Closed PRs: " + "; ".join(closed_prs))
    if release_titles:
        parts.append("Releases: " + "; ".join(release_titles))
    return ". ".join(parts)[:2000] or "No recent progress found."


def suggest_next_task(row, issues, pulls, workflows):
    open_pr = next((item for item in pulls if item.get("state") == "open" and not item.get("draft")), None)
    if open_pr:
        return f"Review or merge PR #{open_pr['number']}: {open_pr['title']}"
    open_issue = next((item for item in issues if item.get("state") == "open"), None)
    if open_issue:
        return f"Work on issue #{open_issue['number']}: {open_issue['title']}"
    inactive_workflow = next((item for item in workflows if item.get("state") not in {"active", ""}), None)
    if inactive_workflow:
        return f"Check workflow: {inactive_workflow['name']}"
    if row.inactive:
        return "Project looks inactive; decide whether to resume, archive, or write a status note."
    return "Write the next milestone and create a focused issue."


def link_repository_to_life_item(row):
    item = LifeItem.query.filter_by(repository=row.html_url).first()
    if item is None:
        item = LifeItem.query.filter(LifeItem.repository.like(f"%{row.repo_full_name}%")).first()
    if item is None:
        title = row.repo_full_name.split("/", 1)[1]
        item = LifeItem(
            source_key=f"github:{row.repo_full_name}",
            title=title,
            description=row.description or "GitHub repository tracked by AiOS.",
            category="project",
            priority="normal",
            status="open",
            repository=row.html_url,
        )
        db.session.add(item)
    item.repository = row.html_url
    item.ai_summary = row.recent_progress
    item.next_action = row.suggested_next_task
    item.progress = row.completion_percentage
    item.analytics_json = _dump_object({"github_completion_percentage": row.completion_percentage, "inactive": row.inactive})
    row.life_item = item
    db.session.flush()
    link_repo_to_matching_life_items(row, item)


def link_repo_to_matching_life_items(row, repo_item):
    repo_name = row.repo_full_name.split("/", 1)[1].lower()
    candidates = LifeItem.query.filter(LifeItem.id != repo_item.id).limit(200).all()
    for candidate in candidates:
        haystack = " ".join([candidate.title or "", candidate.description or "", candidate.repository or "", candidate.tags_json or ""]).lower()
        if repo_name not in haystack and row.repo_full_name.lower() not in haystack:
            continue
        exists = LifeItemRelation.query.filter_by(
            source_item_id=repo_item.id,
            target_item_id=candidate.id,
            relation_type="github_repository",
        ).first()
        if exists:
            continue
        db.session.add(
            LifeItemRelation(
                source_item=repo_item,
                target_item=candidate,
                relation_type="github_repository",
                strength=0.8,
                reason=f"Repository context matched {row.repo_full_name}.",
                metadata_json=_dump_object({"repo": row.repo_full_name}),
            )
        )


def refresh_planning_events(row):
    summary = format_planning_activity(row)
    for event in PlanningEvent.query.filter(PlanningEvent.repo_url.like(f"%{row.repo_full_name}%")).all():
        event.repo_latest_activity = summary
        if not event.work_done and row.recent_progress:
            event.work_done = row.recent_progress[:2000]
        if row.remaining_work:
            event.work_left = row.remaining_work[:2000]
        event.next_question = f"What changed in {row.repo_full_name}, and should the next task still be: {row.suggested_next_task}?"


def format_planning_activity(row):
    issues = _json(row.issues_json)
    prs = _json(row.pull_requests_json)
    open_issues = sum(1 for item in issues if item.get("state") == "open")
    open_prs = sum(1 for item in prs if item.get("state") == "open")
    status = "Inactive" if row.inactive else "Active"
    return (
        f"{row.recent_progress}. Open GitHub work: {open_issues} issues, {open_prs} PRs. "
        f"{status}. Completion estimate: {row.completion_percentage}%. Next: {row.suggested_next_task}"
    )[:2000]


def generate_daily_summary(summary_date=None):
    summary_date = summary_date or date.today()
    rows = GitHubRepository.query.order_by(GitHubRepository.last_synced_at.desc()).limit(50).all()
    inactive = [row for row in rows if row.inactive]
    tasks = [row.suggested_next_task for row in rows if row.suggested_next_task][:8]
    if rows:
        avg_completion = round(sum(row.completion_percentage for row in rows) / len(rows))
        summary = f"{len(rows)} repositories tracked. Average completion {avg_completion}%. {len(inactive)} inactive projects need review."
    else:
        summary = "No GitHub repositories linked yet."
    daily = GitHubDailySummary.query.filter_by(summary_date=summary_date).first()
    if daily is None:
        daily = GitHubDailySummary(summary_date=summary_date, summary=summary)
        db.session.add(daily)
    daily.summary = summary
    daily.repo_count = len(rows)
    daily.inactive_count = len(inactive)
    daily.suggested_tasks_json = _dump(tasks)
    daily.repositories_json = _dump([serialize_repository(row) for row in rows])
    return daily


def serialize_repository(row):
    return {
        "id": row.id,
        "repo": row.repo_full_name,
        "url": row.html_url,
        "life_item_id": row.life_item_id,
        "description": row.description or "",
        "default_branch": row.default_branch or "",
        "primary_language": row.primary_language or "",
        "inactive": row.inactive,
        "completion_percentage": row.completion_percentage,
        "current_sprint": row.current_sprint or "",
        "remaining_work": row.remaining_work or "",
        "recent_progress": row.recent_progress or "",
        "suggested_next_task": row.suggested_next_task or "",
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        "counts": _json(row.raw_json, {}).get("counts", {}),
    }


def serialize_daily_summary(row):
    return {
        "date": row.summary_date.isoformat(),
        "summary": row.summary,
        "repo_count": row.repo_count,
        "inactive_count": row.inactive_count,
        "suggested_tasks": _json(row.suggested_tasks_json),
        "repositories": _json(row.repositories_json),
    }
