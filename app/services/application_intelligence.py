import hashlib
import json
import re
from datetime import date, datetime
from email.utils import parseaddr

from app.models import ConnectedAccount, EmailMessage, LifeItem, Opportunity, db
from app.services.placements import is_neopat_signal


ACTIVE_APPLICATION_LIMIT = 100
APPLICATION_STAGES = {
    "tracked": 0,
    "applied": 1,
    "shortlisted": 2,
    "assessment": 3,
    "project": 4,
    "interview": 5,
    "offer": 6,
    "rejected": 7,
}
ACTION_STAGES = {"shortlisted", "assessment", "project", "interview", "offer"}
APPLICATION_CUES = (
    "application received",
    "application submitted",
    "successfully applied",
    "thank you for applying",
    "thanks for applying",
    "we received your application",
    "your application for",
    "candidate application",
)


def application_overview(active_limit=ACTIVE_APPLICATION_LIMIT):
    grouped = {}
    projects = _project_candidates()
    rows = (
        Opportunity.query.filter(Opportunity.kind.in_(("job", "internship", "career")))
        .order_by(Opportunity.updated_at.desc())
        .all()
    )
    for opportunity in rows:
        if is_neopat_signal(
            opportunity.title,
            opportunity.organization,
            opportunity.source,
            opportunity.notes,
        ):
            continue
        email = (
            db.session.get(EmailMessage, opportunity.email_message_id)
            if opportunity.email_message_id
            else None
        )
        updates = sorted(
            opportunity.placement_updates,
            key=lambda item: item.occurred_at or item.created_at,
        )
        text = _signal_text(opportunity, email, updates)
        stage = _stage(opportunity.status, text)
        if not _is_application(stage, text, updates):
            continue

        company = _company(opportunity, email)
        key = _normalize(company) or f"opportunity-{opportunity.id}"
        group = grouped.setdefault(
            key,
            {
                "company": company,
                "roles": [],
                "stage_events": [],
                "applied_dates": [],
                "latest_dates": [],
                "deadlines": [],
                "platforms": [],
                "accounts": [],
                "emails": [],
                "timeline": [],
                "summaries": [],
                "actions": [],
                "opportunity_ids": [],
                "inferred_applied_date": False,
            },
        )
        role = _role(opportunity.title, company)
        _append_unique(group["roles"], role)
        group["opportunity_ids"].append(opportunity.id)
        latest_at = opportunity.updated_at or opportunity.created_at
        group["latest_dates"].append(latest_at)
        group["stage_events"].append((latest_at, stage))
        if opportunity.deadline:
            group["deadlines"].append(opportunity.deadline)

        explicit_applied_at = _explicit_applied_at(opportunity, email, updates, text)
        if explicit_applied_at:
            group["applied_dates"].append(explicit_applied_at)
        elif stage != "tracked":
            inferred = (email.sent_at if email else None) or opportunity.created_at
            group["applied_dates"].append(inferred)
            group["inferred_applied_date"] = True

        platform = _platform(opportunity, email, text)
        _append_unique(group["platforms"], platform)
        if email and email.account:
            _append_unique(group["accounts"], email.account.email)
        if email:
            group["emails"].append(_serialize_source_email(email, platform))
            group["timeline"].append(
                {
                    "at": (email.sent_at or email.created_at).isoformat(),
                    "stage": stage,
                    "title": email.subject or opportunity.title,
                    "summary": _email_summary(email),
                    "source_email_id": email.id,
                    "account_email": email.account.email if email.account else "",
                }
            )
            summary = _email_summary(email)
            if summary:
                _append_unique(group["summaries"], summary)

        for update in updates:
            update_stage = _stage(update.event_type, f"{update.title} {update.summary or ''}")
            happened_at = update.occurred_at or update.created_at
            group["latest_dates"].append(happened_at)
            group["stage_events"].append((happened_at, update_stage))
            if update.deadline:
                group["deadlines"].append(update.deadline)
            if update.action_needed:
                _append_unique(group["actions"], update.action_needed)
            group["timeline"].append(
                {
                    "at": happened_at.isoformat(),
                    "stage": update_stage,
                    "title": update.title,
                    "summary": (update.summary or "")[:500],
                    "source_email_id": email.id if email else None,
                    "account_email": email.account.email if email and email.account else "",
                }
            )

    applications = [_serialize_group(key, value, projects) for key, value in grouped.items()]
    applications.sort(key=_application_sort_key, reverse=True)
    active = applications[: max(1, int(active_limit or ACTIVE_APPLICATION_LIMIT))]
    archived = applications[len(active) :]
    for item in archived:
        item["archived"] = True

    return {
        "ok": True,
        "active": active,
        "archive": archived,
        "stats": {
            "active": len(active),
            "archived": len(archived),
            "needs_action": sum(item["needs_action"] for item in active),
            "next_steps": sum(item["selected_for_next_step"] for item in active),
            "offers": sum(item["stage"] == "offer" for item in active),
            "emails_scanned": EmailMessage.query.count(),
            "accounts": ConnectedAccount.query.filter_by(provider="google").count(),
        },
        "today": [item for item in active if item["needs_action"] and item["days_left"] is not None and item["days_left"] <= 0][:8],
        "due_soon": [item for item in active if item["days_left"] is not None and 0 < item["days_left"] <= 7][:8],
        "updated_at": datetime.utcnow().isoformat(),
    }


def _serialize_group(key, group, projects):
    stage = max(
        group["stage_events"],
        key=lambda value: (value[0], APPLICATION_STAGES.get(value[1], 0)),
    )[1]
    applied_at = min(group["applied_dates"]) if group["applied_dates"] else None
    latest_at = max(group["latest_dates"]) if group["latest_dates"] else applied_at
    upcoming = [deadline for deadline in group["deadlines"] if deadline.date() >= date.today()]
    deadline = min(upcoming) if upcoming else (max(group["deadlines"]) if group["deadlines"] else None)
    days_left = (deadline.date() - date.today()).days if deadline else None
    timeline = _dedupe_timeline(group["timeline"])
    emails = _dedupe_emails(group["emails"])
    role = group["roles"][0] if group["roles"] else "Application"
    project = _linked_project(group["company"], group["roles"], projects)
    action = next((value for value in reversed(group["actions"]) if value), "") or _next_action(stage, group["company"], role)
    needs_action = stage in ACTION_STAGES or (days_left is not None and days_left <= 7)
    stable_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return {
        "id": stable_id,
        "company": group["company"],
        "role": role,
        "roles": group["roles"],
        "stage": stage,
        "stage_label": _stage_label(stage),
        "selected_for_next_step": stage in ACTION_STAGES,
        "needs_action": needs_action,
        "applied_at": applied_at.isoformat() if applied_at else None,
        "applied_date_inferred": bool(group["inferred_applied_date"]),
        "latest_activity_at": latest_at.isoformat() if latest_at else None,
        "deadline": deadline.isoformat() if deadline else None,
        "days_left": days_left,
        "platform": group["platforms"][0] if group["platforms"] else "Email",
        "platforms": group["platforms"],
        "source_accounts": group["accounts"],
        "source_email": emails[0] if emails else None,
        "source_emails": emails[:12],
        "summary": "\n".join(group["summaries"][:3]),
        "next_action": action,
        "timeline": timeline[:20],
        "project": project,
        "opportunity_ids": group["opportunity_ids"],
        "archived": False,
    }


def _signal_text(opportunity, email, updates):
    values = [opportunity.title, opportunity.status, opportunity.source, opportunity.notes]
    if email:
        values.extend([email.sender, email.subject, email.snippet, email.body_text])
    for update in updates:
        values.extend([update.event_type, update.title, update.summary, update.action_needed])
    return " ".join(str(value or "") for value in values).lower()


def _is_application(stage, text, updates):
    if stage != "tracked":
        return True
    return bool(updates) and any(update.event_type != "opening" for update in updates) or any(cue in text for cue in APPLICATION_CUES)


def _stage(current, text):
    lowered = f"{current or ''} {text or ''}".lower()
    rules = (
        ("offer", ("offer letter", "pleased to offer", "employment offer")),
        ("rejected", ("unfortunately", "not moving forward", "not selected", "rejected")),
        ("interview", ("interview scheduled", "technical interview", "hr interview", "manager round")),
        ("project", ("project submission", "take home assignment", "take-home assignment", "case study")),
        ("assessment", ("online assessment", "coding assessment", "oa received", "test link", "online test")),
        ("shortlisted", ("shortlisted", "selected for round", "next round", "qualified")),
        ("applied", APPLICATION_CUES + (" applied ",)),
    )
    for stage, phrases in rules:
        if any(phrase in f" {lowered} " for phrase in phrases):
            return stage
    normalized = _normalize(current)
    aliases = {
        "interview scheduled": "interview",
        "oa received": "assessment",
        "shortlisted": "shortlisted",
        "offer": "offer",
        "rejected": "rejected",
        "applied": "applied",
    }
    return aliases.get(normalized, "tracked")


def _explicit_applied_at(opportunity, email, updates, text):
    values = [
        update.occurred_at or update.created_at
        for update in updates
        if update.event_type == "application" or "applied" in _normalize(update.title)
    ]
    if values:
        return min(values)
    if any(cue in text for cue in APPLICATION_CUES) or _normalize(opportunity.status) == "applied":
        return (email.sent_at if email else None) or opportunity.created_at
    return None


def _company(opportunity, email):
    current = str(opportunity.organization or "").strip()
    if current and _normalize(current) not in {"unknown", "email", "placement office"}:
        return current
    if email and email.insight:
        companies = _json_list(email.insight.companies_json)
        if companies:
            return str(companies[0])[:120]
    _name, address = parseaddr(email.sender if email else opportunity.source or "")
    domain = address.split("@", 1)[-1].split(".", 1)[0] if "@" in address else ""
    return domain.replace("-", " ").title() or current or "Unknown company"


def _role(title, company):
    value = re.sub(r"^(re|fwd|fw):\s*", "", str(title or ""), flags=re.I).strip()
    for phrase in ("application received for", "thank you for applying for", "your application for"):
        if phrase in value.lower():
            value = value[value.lower().index(phrase) + len(phrase) :].strip(" :-")
    if company and value.lower().startswith(company.lower()):
        value = value[len(company) :].strip(" :-")
    return value[:180] or "Application"


def _platform(opportunity, email, text):
    sender = (email.sender if email else opportunity.source or "").lower()
    joined = f"{sender} {text}"
    rules = (
        ("LinkedIn", ("linkedin.com", "linkedin jobs")),
        ("Indeed", ("indeed.com",)),
        ("Naukri", ("naukri.com",)),
        ("Wellfound", ("wellfound.com", "angel.co")),
        ("Greenhouse", ("greenhouse.io", "greenhouse")),
        ("Lever", ("lever.co",)),
        ("Workable", ("workablemail.com", "workable.com")),
        ("SmartRecruiters", ("smartrecruiters.com",)),
        ("College placement", ("vitbhopal.ac.in", "placement office", "cdc info")),
    )
    for label, cues in rules:
        if any(cue in joined for cue in cues):
            return label
    if email and email.account and parseaddr(email.sender)[1].lower() == email.account.email.lower():
        return "Direct email"
    return "Company website" if email else (opportunity.source or "Email")


def _serialize_source_email(email, platform):
    return {
        "id": email.id,
        "account_email": email.account.email if email.account else "",
        "sender": email.sender or "",
        "subject": email.subject or "",
        "received_at": (email.sent_at or email.created_at).isoformat(),
        "platform": platform,
    }


def _email_summary(email):
    if email.insight and email.insight.summary:
        return re.sub(r"\s+", " ", email.insight.summary).strip()[:500]
    return re.sub(r"\s+", " ", email.snippet or "").strip()[:500]


def _project_candidates():
    return (
        LifeItem.query.filter(
            (LifeItem.category == "project")
            | ((LifeItem.repository.isnot(None)) & (LifeItem.repository != ""))
            | ((LifeItem.working_directory.isnot(None)) & (LifeItem.working_directory != ""))
        )
        .order_by(LifeItem.updated_at.desc())
        .all()
    )


def _linked_project(company, roles, projects):
    terms = set(_normalize(f"{company} {' '.join(roles)}").split()) - {"intern", "internship", "engineer", "developer", "application"}
    best = None
    best_score = 0
    for item in projects:
        haystack = set(_normalize(f"{item.title} {item.description or ''} {item.tags_json or ''}").split())
        score = len(terms & haystack)
        if score > best_score:
            best, best_score = item, score
    if best is None or best_score == 0:
        return None
    history = _json_list(best.history_json)
    signals = []
    if best.working_directory:
        signals.append("local_workspace")
    if best.repository:
        signals.append("github")
    if any("codex" in str(entry).lower() for entry in history):
        signals.append("codex_history")
    return {
        "id": best.id,
        "title": best.title,
        "progress": round(float(best.progress or 0)),
        "repository": best.repository or "",
        "working_directory": best.working_directory or "",
        "next_action": best.next_action or "",
        "signals": signals,
    }


def _next_action(stage, company, role):
    actions = {
        "applied": f"Watch {company} for an assessment or recruiter reply.",
        "shortlisted": f"Read the next-round instructions for {role} and reserve preparation time.",
        "assessment": f"Open the assessment mail, verify the link, and complete the test before its deadline.",
        "project": f"Create or link the project workspace, then finish the highest-risk submission work first.",
        "interview": f"Confirm the interview slot and prepare a project walkthrough plus role-specific questions.",
        "offer": f"Review the offer, compensation, joining date, and acceptance deadline.",
        "rejected": f"Archive the application and keep any useful feedback.",
    }
    return actions.get(stage, f"Review the latest email from {company} and classify the next step.")


def _stage_label(stage):
    return {
        "assessment": "Assessment / test",
        "project": "Project submission",
        "interview": "Interview scheduled",
        "shortlisted": "Selected for next round",
        "offer": "Offer received",
        "rejected": "Closed / rejected",
        "applied": "Applied",
    }.get(stage, "Tracking")


def _dedupe_timeline(values):
    output = []
    seen = set()
    for item in sorted(values, key=lambda value: value.get("at") or "", reverse=True):
        key = (item.get("stage"), _normalize(item.get("title")), item.get("source_email_id"))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _dedupe_emails(values):
    output = []
    seen = set()
    for item in sorted(values, key=lambda value: value.get("received_at") or "", reverse=True):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        output.append(item)
    return output


def _application_sort_key(item):
    return item["applied_at"] or item["latest_activity_at"] or ""


def _json_list(value):
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _append_unique(values, value):
    if value and value not in values:
        values.append(value)


def _normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
