import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from app.models import (
    ActivityEvent,
    DailyAssistantEntry,
    EmailMessage,
    GitHubRepository,
    GoalPlan,
    LearningItem,
    LifeItem,
    Opportunity,
    PlanTask,
    PlanTaskSession,
    PlanningEvent,
)


DONE_STATUSES = {"completed", "done"}
CODING_CATEGORIES = {"coding", "development", "programming", "code", "deep_work", "productivity"}
LEARNING_CATEGORIES = {"learning", "study", "course", "research", "notes"}
FOCUS_CATEGORIES = {"coding", "development", "programming", "deep_work", "focus", "productivity", "learning", "study"}
VALID_PERIODS = {"daily", "weekly", "monthly", "yearly"}


def analytics_report(period="daily", anchor=None):
    period = str(period or "daily").lower()
    if period not in VALID_PERIODS:
        period = "daily"
    anchor = parse_date(anchor) or date.today()
    start, end = period_range(period, anchor)
    prior_start, prior_end = prior_period_range(period, start, end)
    metrics = collect_metrics(start, end)
    prior = collect_metrics(prior_start, prior_end)
    trends = metric_trends(metrics, prior)
    burnout = predict_burnout(metrics, activity_by_day(start - timedelta(days=13), end))
    inactivity = detect_inactivity(anchor)
    workload = suggest_workload_balancing(metrics, burnout, inactivity)
    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "metrics": metrics,
        "trends": trends,
        "streaks": streaks(anchor),
        "burnout": burnout,
        "inactivity": inactivity,
        "workload_balance": workload,
        "summary": summarize_report(period, metrics, burnout, inactivity),
    }


def analytics_overview(anchor=None):
    anchor = parse_date(anchor) or date.today()
    return {
        "ok": True,
        "anchor": anchor.isoformat(),
        "reports": {period: analytics_report(period, anchor) for period in ["daily", "weekly", "monthly", "yearly"]},
    }


def collect_metrics(start, end):
    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)
    activities = ActivityEvent.query.filter(ActivityEvent.created_at.between(start_dt, end_dt)).all()
    sessions = PlanTaskSession.query.filter(PlanTaskSession.started_at.between(start_dt, end_dt)).all()
    events = PlanningEvent.query.filter(PlanningEvent.updated_at.between(start_dt, end_dt)).all()
    emails = EmailMessage.query.filter(EmailMessage.created_at.between(start_dt, end_dt)).all()
    learning = LearningItem.query.filter(LearningItem.updated_at.between(start_dt, end_dt)).all()
    opportunities = Opportunity.query.filter(Opportunity.updated_at.between(start_dt, end_dt)).all()
    plans = GoalPlan.query.filter(GoalPlan.updated_at.between(start_dt, end_dt)).all()
    assistant = DailyAssistantEntry.query.filter(DailyAssistantEntry.entry_date.between(start, end)).all()
    repos = GitHubRepository.query.all()
    life_items = LifeItem.query.filter(LifeItem.updated_at.between(start_dt, end_dt)).all()

    activity_minutes = sum(max(0, item.duration_minutes or 0) for item in activities)
    session_minutes = sum(max(0, item.duration_minutes or 0) for item in sessions)
    assistant_hours = sum(entry.estimated_hours or 0 for entry in assistant if entry.kind == "evening_response")
    coding_minutes = sum_activity_minutes(activities, CODING_CATEGORIES) + github_coding_minutes(repos, start, end)
    learning_minutes = sum_activity_minutes(activities, LEARNING_CATEGORIES) + sum(item.estimated_minutes or 0 for item in learning)
    focus_minutes = sum_activity_minutes(activities, FOCUS_CATEGORIES) + session_minutes
    commits = commits_in_range(repos, start, end)
    completed_events = [event for event in events if event.status in DONE_STATUSES]
    completed_tasks = PlanTask.query.filter(
        PlanTask.completed_at.isnot(None),
        PlanTask.completed_at.between(start_dt, end_dt),
    ).all()

    projects = {
        item.project
        for item in events
        if item.project
    } | {
        item.title
        for item in life_items
        if item.category in {"project", "goal", "research"}
    } | {
        repo.repo_full_name for repo in repos if repo.updated_at and start_dt <= repo.updated_at <= end_dt
    }
    hackathons = [item for item in opportunities if item.kind.lower() == "hackathon"]
    internships = [
        item
        for item in opportunities
        if item.kind.lower() in {"internship", "placement", "job"}
        or "intern" in item.title.lower()
    ]
    completed_goals = [plan for plan in plans if plan.status == "completed"]

    return {
        "coding_hours": round(coding_minutes / 60, 2),
        "learning_hours": round(learning_minutes / 60, 2),
        "projects": len(projects),
        "hackathons": len(hackathons),
        "internships": len(internships),
        "emails": len(emails),
        "commits": len(commits),
        "tasks_completed": len(completed_events) + len(completed_tasks),
        "goals_completed": len(completed_goals),
        "focus_time_hours": round(focus_minutes / 60, 2),
        "activity_hours": round((activity_minutes + session_minutes + assistant_hours * 60) / 60, 2),
        "open_tasks": PlanningEvent.query.filter(PlanningEvent.status.notin_(list(DONE_STATUSES))).count(),
        "blocked_tasks": PlanningEvent.query.filter_by(status="blocked").count(),
        "overdue_tasks": overdue_task_count(end),
        "commits_detail": commits[:10],
    }


def sum_activity_minutes(activities, categories):
    return sum(
        max(0, item.duration_minutes or 0)
        for item in activities
        if str(item.category or "").lower() in categories
    )


def github_coding_minutes(repos, start, end):
    return len(commits_in_range(repos, start, end)) * 30


def commits_in_range(repos, start, end):
    commits = []
    for repo in repos:
        for item in load_json(repo.commits_json):
            when = parse_datetime(item.get("date"))
            if when and start <= when.date() <= end:
                commits.append(
                    {
                        "repo": repo.repo_full_name,
                        "sha": item.get("sha"),
                        "message": item.get("message") or "",
                        "date": when.isoformat(),
                    }
                )
    commits.sort(key=lambda item: item["date"], reverse=True)
    return commits


def overdue_task_count(anchor):
    anchor_dt = datetime.combine(anchor, time.max)
    return PlanningEvent.query.filter(
        PlanningEvent.deadline.isnot(None),
        PlanningEvent.deadline < anchor_dt,
        PlanningEvent.status.notin_(list(DONE_STATUSES)),
    ).count()


def metric_trends(current, prior):
    fields = [
        "coding_hours",
        "learning_hours",
        "projects",
        "hackathons",
        "internships",
        "emails",
        "commits",
        "tasks_completed",
        "goals_completed",
        "focus_time_hours",
    ]
    return {field: trend_value(current.get(field, 0), prior.get(field, 0)) for field in fields}


def trend_value(current, previous):
    delta = round((current or 0) - (previous or 0), 2)
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    return {"current": current, "previous": previous, "delta": delta, "direction": direction}


def predict_burnout(metrics, daily_minutes):
    active_days = [minutes for minutes in daily_minutes.values() if minutes > 0]
    average_hours = (sum(active_days) / len(active_days) / 60) if active_days else 0
    intense_days = sum(1 for minutes in daily_minutes.values() if minutes >= 8 * 60)
    blocked = metrics.get("blocked_tasks", 0)
    overdue = metrics.get("overdue_tasks", 0)
    score = 0
    score += 35 if average_hours >= 8 else 20 if average_hours >= 6 else 0
    score += min(25, intense_days * 5)
    score += min(20, blocked * 4)
    score += min(20, overdue * 5)
    level = "high" if score >= 65 else "medium" if score >= 35 else "low"
    reasons = []
    if average_hours >= 6:
        reasons.append(f"{round(average_hours, 1)}h average active workload")
    if intense_days:
        reasons.append(f"{intense_days} intense day{'s' if intense_days != 1 else ''}")
    if blocked:
        reasons.append(f"{blocked} blocked task{'s' if blocked != 1 else ''}")
    if overdue:
        reasons.append(f"{overdue} overdue task{'s' if overdue != 1 else ''}")
    if not reasons:
        reasons.append("workload signals look balanced")
    return {"level": level, "score": score, "average_daily_hours": round(average_hours, 2), "reasons": reasons}


def detect_inactivity(anchor):
    latest = latest_activity_date()
    if latest is None:
        return {
            "inactive": True,
            "days_since_activity": None,
            "last_activity_date": None,
            "message": "No activity has been tracked yet.",
        }
    days = max(0, (anchor - latest).days)
    return {
        "inactive": days >= 3,
        "days_since_activity": days,
        "last_activity_date": latest.isoformat(),
        "message": "No meaningful activity for 3+ days." if days >= 3 else "Activity is current.",
    }


def latest_activity_date():
    candidates = []
    for value in [
        max_date(ActivityEvent.created_at),
        max_date(PlanningEvent.updated_at),
        max_date(PlanTask.completed_at),
        max_date(EmailMessage.created_at),
        max_commit_date(GitHubRepository.query.all()),
        max_date(LearningItem.updated_at),
    ]:
        if value:
            candidates.append(value.date())
    return max(candidates) if candidates else None


def max_date(column):
    model = column.class_
    row = model.query.filter(column.isnot(None)).order_by(column.desc()).first()
    return getattr(row, column.key) if row else None


def max_commit_date(repos):
    dates = []
    for item in commits_in_range(repos, date(1970, 1, 1), date(2999, 12, 31)):
        when = parse_datetime(item.get("date"))
        if when:
            dates.append(when)
    return max(dates) if dates else None


def suggest_workload_balancing(metrics, burnout, inactivity):
    suggestions = []
    if burnout["level"] == "high":
        suggestions.append("Move one non-urgent task out of today and protect a recovery block.")
    elif burnout["level"] == "medium":
        suggestions.append("Cap deep work to two focused blocks and leave space for admin cleanup.")
    if inactivity["inactive"]:
        suggestions.append("Restart with a 25-minute low-friction task from the highest-priority project.")
    if metrics.get("blocked_tasks", 0):
        suggestions.append("Resolve or ask for help on blocked tasks before adding new commitments.")
    if metrics.get("learning_hours", 0) == 0 and metrics.get("coding_hours", 0) >= 4:
        suggestions.append("Add a short learning/review block to avoid only shipping without consolidating.")
    if metrics.get("coding_hours", 0) == 0 and metrics.get("learning_hours", 0) >= 3:
        suggestions.append("Turn learning into one small build task so progress becomes concrete.")
    if not suggestions:
        suggestions.append("Workload looks balanced. Keep one focused block and one review block.")
    return suggestions


def streaks(anchor):
    daily = activity_by_day(anchor - timedelta(days=365), anchor)
    return {
        "active_days": consecutive_days(daily, anchor, lambda minutes: minutes > 0),
        "focus_days": consecutive_days(daily, anchor, lambda minutes: minutes >= 45),
        "coding_days": consecutive_category_days(anchor, CODING_CATEGORIES),
        "learning_days": consecutive_category_days(anchor, LEARNING_CATEGORIES),
    }


def consecutive_days(daily, anchor, predicate):
    count = 0
    cursor = anchor
    while predicate(daily.get(cursor, 0)):
        count += 1
        cursor -= timedelta(days=1)
    return count


def consecutive_category_days(anchor, categories):
    rows = ActivityEvent.query.filter(ActivityEvent.created_at >= datetime.combine(anchor - timedelta(days=365), time.min)).all()
    daily = defaultdict(int)
    for row in rows:
        if str(row.category or "").lower() in categories:
            daily[row.created_at.date()] += max(0, row.duration_minutes or 0)
    return consecutive_days(daily, anchor, lambda minutes: minutes > 0)


def activity_by_day(start, end):
    daily = defaultdict(int)
    rows = ActivityEvent.query.filter(
        ActivityEvent.created_at.between(datetime.combine(start, time.min), datetime.combine(end, time.max))
    ).all()
    for row in rows:
        daily[row.created_at.date()] += max(0, row.duration_minutes or 0)
    sessions = PlanTaskSession.query.filter(
        PlanTaskSession.started_at.between(datetime.combine(start, time.min), datetime.combine(end, time.max))
    ).all()
    for row in sessions:
        daily[row.started_at.date()] += max(0, row.duration_minutes or 0)
    return daily


def summarize_report(period, metrics, burnout, inactivity):
    return (
        f"{period.title()} analytics: {metrics['focus_time_hours']}h focus, "
        f"{metrics['coding_hours']}h coding, {metrics['learning_hours']}h learning, "
        f"{metrics['tasks_completed']} task completions. Burnout risk is {burnout['level']}; "
        f"{inactivity['message']}"
    )


def period_range(period, anchor):
    if period == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    if period == "monthly":
        start = anchor.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        return start, next_month - timedelta(days=1)
    if period == "yearly":
        return date(anchor.year, 1, 1), date(anchor.year, 12, 31)
    return anchor, anchor


def prior_period_range(period, start, end):
    length = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    if period == "monthly":
        prior_anchor = start - timedelta(days=1)
        return period_range("monthly", prior_anchor)
    if period == "yearly":
        return date(start.year - 1, 1, 1), date(start.year - 1, 12, 31)
    return prior_end - timedelta(days=length - 1), prior_end


def parse_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def load_json(value):
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []
