import hashlib
import html
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from email.utils import parseaddr

from app.models import ConnectedAccount, EmailMessage, LifeItem, Opportunity, db
from app.services.email_scope import EMAIL_PORTFOLIO_LIMIT, latest_emails_combined
from app.services.placements import is_neopat_signal


ACTIVE_APPLICATION_LIMIT = 100
NO_RESPONSE_DAYS = 7
SELECTED_STAGES = {"shortlisted", "assessment", "project", "interview", "offer"}
APPLICATION_STAGES = {
    "applied": 1,
    "shortlisted": 2,
    "assessment": 3,
    "project": 4,
    "interview": 5,
    "offer": 6,
    "rejected": 7,
}

APPLICATION_CUES = (
    "application received",
    "application submitted",
    "application confirmation",
    "successfully applied",
    "thank you for applying",
    "thanks for applying",
    "we received your application",
    "we have received your application",
    "your application has been received",
    "your application was received",
    "your application was sent to",
    "your application was viewed by",
    "your application to",
    "candidate application",
    "application status",
    "next steps for your job application",
)
SELECTION_CUES = (
    "you have been shortlisted",
    "you've been shortlisted",
    "you are shortlisted",
    "selected for the next round",
    "selected for next round",
    "advanced to the next round",
    "qualified for the next round",
    "your application has progressed",
    "move forward with your application",
    "moving forward with your application",
    "your profile is eligible for the next round",
    "you are eligible for the next round",
)
ASSESSMENT_CUES = (
    "your online assessment",
    "complete the online assessment",
    "coding assessment invitation",
    "assessment for your application",
    "assessment link",
    "online test link",
    "take-home assessment",
    "take home assessment",
)
INTERVIEW_CUES = (
    "interview scheduled",
    "invite you to interview",
    "invitation to interview",
    "your interview",
    "interview with our",
    "schedule your interview",
    "confirm your interview",
    "technical interview round",
    "hr interview round",
)
PROJECT_CUES = (
    "take-home assignment",
    "take home assignment",
    "project submission for your application",
    "case study round",
    "project round",
)
OFFER_CUES = (
    "offer letter",
    "pleased to offer you",
    "employment offer",
    "offer of employment",
)
REJECTION_CUES = (
    "unfortunately",
    "not moving forward",
    "will not be moving forward",
    "not selected for this position",
    "we regret to inform you",
    "application was unsuccessful",
)
CAREER_NOISE_CUES = (
    "job alert",
    "jobs you may be interested",
    "jobs in ",
    "job openings in",
    "apply now",
    "recommended jobs",
    "new jobs",
    "hottest early to mid career jobs",
    "want to connect",
    "you have an invitation",
    "recently posted",
    "your posts got",
    "interview prep",
    "resume tips",
    "hiring challenges",
    " is hiring",
    "hiring for",
    "applications open",
    "pre placement talk",
    "applied students",
    "campus recruitment",
    "just messaged you",
    "messaged you",
    "requested to connect",
    "complete your application to",
)
GENERIC_SELECTION_CUES = (
    "selection list",
    "selected candidates",
    "shortlisted candidates",
    "eligible candidates",
)
GENERIC_COMPANIES = {
    "",
    "email",
    "google",
    "github",
    "linkedin",
    "indeed",
    "glassdoor",
    "workday",
    "myworkday",
    "greenhouse",
    "lever",
    "keka",
    "kekamail",
    "unstop",
    "hack2skill",
    "hackerearth",
    "devfolio",
    "placement office",
    "vitbhopal",
    "vitstudent",
    "unknown",
}
ATS_DOMAINS = {
    "ashbyhq",
    "greenhouse",
    "indeed",
    "jobgether",
    "kekamail",
    "lever",
    "linkedin",
    "myworkday",
    "smartrecruiters",
    "unstop",
    "workable",
    "workday",
}
HACKATHON_TERMS = (
    "hackathon",
    "buildathon",
    "datathon",
    "devpost",
    "hack2skill",
    "hackerearth",
    "devfolio",
)


def application_overview(
    active_limit=ACTIVE_APPLICATION_LIMIT,
    mail_limit=EMAIL_PORTFOLIO_LIMIT,
):
    emails = latest_emails_combined(mail_limit)
    projects = _project_candidates()
    opportunities = {
        item.email_message_id: item
        for item in Opportunity.query.filter(
            Opportunity.email_message_id.isnot(None),
            Opportunity.kind.in_(("job", "internship", "career")),
        ).all()
    }
    grouped = {}
    career_signals = {}
    hackathon_signals = {}

    for email in emails:
        opportunity = opportunities.get(email.id)
        career = classify_career_email(email, opportunity)
        if career:
            career_signals[email.id] = career
            key = _application_group_key(career, email)
            group = grouped.setdefault(key, _new_application_group(career))
            _add_application_signal(group, email, career, opportunity)
            continue
        hackathon = classify_hackathon_email(email)
        if hackathon:
            hackathon_signals[email.id] = hackathon

    applications = [
        _serialize_group(key, value, projects)
        for key, value in grouped.items()
    ]
    applications.sort(key=_application_sort_key, reverse=True)
    active_limit = max(1, int(active_limit or ACTIVE_APPLICATION_LIMIT))
    active = applications[:active_limit]
    archived = applications[active_limit:]
    for item in archived:
        item["archived"] = True

    all_items = active + archived
    selected = sum(item["selected_for_next_step"] for item in all_items)
    no_response = sum(item["response_status"] == "no_response" for item in all_items)
    no_further_email = sum(not item["has_further_email"] for item in all_items)
    applied = len(all_items)
    accounts_scanned = len({email.account_id for email in emails})
    stats = {
        "active": len(active),
        "archived": len(archived),
        "total": applied,
        "applied": applied,
        "selected": selected,
        "selected_rate": round(selected / applied * 100) if applied else 0,
        "no_response": no_response,
        "no_further_email": no_further_email,
        "awaiting_response": sum(
            item["response_status"] == "awaiting_response"
            for item in all_items
        ),
        "rejected": sum(item["stage"] == "rejected" for item in all_items),
        "needs_action": sum(item["needs_action"] for item in active),
        "next_steps": selected,
        "offers": sum(item["stage"] == "offer" for item in all_items),
        "emails_scanned": len(emails),
        "emails_available": EmailMessage.query.count(),
        "scan_limit": EMAIL_PORTFOLIO_LIMIT,
        "accounts": ConnectedAccount.query.filter_by(provider="google").count(),
        "accounts_scanned": accounts_scanned,
    }
    return {
        "ok": True,
        "scope": {
            "label": f"Latest {EMAIL_PORTFOLIO_LIMIT} combined emails",
            "limit": EMAIL_PORTFOLIO_LIMIT,
            "emails_scanned": len(emails),
            "accounts_scanned": accounts_scanned,
        },
        "active": active,
        "archive": archived,
        "stats": stats,
        "status_counts": _status_counts(all_items),
        "mail_categories": _mail_category_counts(
            emails,
            career_signals,
            hackathon_signals,
        ),
        "hackathons": _hackathon_overview(emails, hackathon_signals),
        "today": [
            item
            for item in active
            if item["needs_action"]
            and item["days_left"] is not None
            and item["days_left"] <= 0
        ][:8],
        "due_soon": [
            item
            for item in active
            if item["days_left"] is not None
            and 0 < item["days_left"] <= 7
        ][:8],
        "updated_at": datetime.utcnow().isoformat(),
    }


def classify_tracked_email(email):
    hackathon = classify_hackathon_email(email)
    if hackathon:
        return hackathon
    return classify_career_email(email)


def classify_career_email(email, opportunity=None):
    text = _email_text(email)
    lowered = text.lower()
    subject = _clean(email.subject).lower()
    labels = set(_json_list(email.labels_json))
    is_sent = "SENT" in labels

    if _is_hackathon_text(lowered):
        return None
    if "complete your application to" in lowered:
        return None
    if _is_generic_career_broadcast(email, lowered, is_sent):
        return None
    direct_stage = _career_stage(lowered, subject, is_sent)
    if (
        not direct_stage
        and email.insight
        and email.insight.category == "internship"
        and not any(cue in lowered for cue in CAREER_NOISE_CUES)
    ):
        direct_stage = _insight_backed_career_stage(email, lowered)
    if not direct_stage:
        return None
    if (
        any(cue in lowered for cue in GENERIC_SELECTION_CUES)
        and not _has_direct_personal_selection(lowered)
        and not is_sent
    ):
        return None
    if (
        any(cue in lowered for cue in CAREER_NOISE_CUES)
        and not _has_direct_application_evidence(lowered, is_sent)
    ):
        return None

    company = _clean_company_name(_company(email, opportunity))
    role = _role(email, company, opportunity)
    occurred_at = email.sent_at or email.created_at
    return {
        "kind": "career",
        "stage": direct_stage,
        "company": company,
        "role": role,
        "platform": _platform(email, lowered),
        "occurred_at": occurred_at,
        "deadline": _opportunity_deadline(opportunity),
        "confidence": _career_confidence(lowered, direct_stage, is_sent),
        "evidence": _career_evidence(lowered, direct_stage, is_sent),
        "status": _stage_label(direct_stage),
    }


def classify_hackathon_email(email):
    text = _email_text(email)
    lowered = text.lower()
    if not _is_hackathon_text(lowered):
        return None
    visible_signal = _clean(
        f"{email.sender or ''} {email.subject or ''} {email.snippet or ''}"
    ).lower()
    if any(
        cue in visible_signal
        for cue in (
            "i want to connect",
            "you have an invitation",
            "view anuranjan",
            "recently posted",
            "build calendar",
            "god bless you",
            "hiring challenges",
            "hackathons just for you",
            "hackathons just dropped",
            "global week of building",
        )
    ):
        return None
    if re.search(r"\b[A-Z][A-Za-z]+\s+registered for\b", _clean(email.subject)):
        return None
    if not _has_specific_hackathon_signal(visible_signal):
        return None
    subject = _clean(email.subject)
    event = _hackathon_name(subject)
    stage = _hackathon_stage(lowered)
    return {
        "kind": "hackathon",
        "opportunity_kind": (
            "competition"
            if re.search(r"\bgrid\s*\d", lowered, re.I)
            else "hackathon"
        ),
        "stage": stage,
        "company": event,
        "role": "Hackathon",
        "event": event,
        "platform": _platform(email, lowered),
        "occurred_at": email.sent_at or email.created_at,
        "deadline": _email_deadline(email),
        "confidence": 0.92 if any(term in lowered for term in HACKATHON_TERMS[:3]) else 0.78,
        "evidence": f"Hackathon mail classified as {stage.replace('_', ' ')}.",
        "status": _hackathon_status_label(stage, text),
    }


def _new_application_group(signal):
    return {
        "company": signal["company"],
        "roles": [],
        "signals": [],
        "deadlines": [],
        "platforms": [],
        "accounts": [],
        "emails": [],
        "summaries": [],
        "opportunity_ids": [],
    }


def _add_application_signal(group, email, signal, opportunity):
    _append_unique(group["roles"], signal["role"])
    _append_unique(group["platforms"], signal["platform"])
    if email.account:
        _append_unique(group["accounts"], email.account.email)
    if opportunity:
        _append_unique(group["opportunity_ids"], opportunity.id)
    if signal["deadline"]:
        group["deadlines"].append(signal["deadline"])
    group["signals"].append(
        {
            **signal,
            "email_id": email.id,
            "subject": _clean(email.subject) or "Application update",
            "summary": _email_summary(email),
            "account_email": email.account.email if email.account else "",
        }
    )
    group["emails"].append(_serialize_source_email(email, signal["platform"]))
    summary = _email_summary(email)
    if summary:
        _append_unique(group["summaries"], summary)


def _serialize_group(key, group, projects):
    signals = sorted(
        group["signals"],
        key=lambda item: item["occurred_at"] or datetime.min,
    )
    latest = signals[-1]
    stage = latest["stage"]
    applied_at = min(
        (item["occurred_at"] for item in signals if item["occurred_at"]),
        default=None,
    )
    latest_at = latest["occurred_at"]
    upcoming = [
        deadline
        for deadline in group["deadlines"]
        if deadline.date() >= date.today()
    ]
    deadline = (
        min(upcoming)
        if upcoming
        else max(group["deadlines"], default=None)
    )
    days_left = (deadline.date() - date.today()).days if deadline else None
    days_waiting = (
        max(0, (datetime.utcnow().date() - applied_at.date()).days)
        if applied_at
        else 0
    )
    emails = _dedupe_emails(group["emails"])
    has_further_email = len(emails) > 1 or stage != "applied"
    response_status = _response_status(
        stage,
        has_further_email,
        days_waiting,
    )
    role = next(
        (value for value in group["roles"] if value != "Application"),
        group["roles"][0] if group["roles"] else "Application",
    )
    project = _linked_project(group["company"], group["roles"], projects)
    needs_action = (
        stage in SELECTED_STAGES
        or (days_left is not None and days_left <= 7)
        or response_status == "no_response"
    )
    confidence = round(
        sum(float(item["confidence"]) for item in signals) / len(signals),
        2,
    )
    stable_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return {
        "id": stable_id,
        "company": group["company"],
        "role": role,
        "roles": group["roles"],
        "stage": stage,
        "stage_label": _stage_label(stage),
        "response_status": response_status,
        "response_label": _response_label(response_status),
        "selected_for_next_step": stage in SELECTED_STAGES,
        "needs_action": needs_action,
        "has_further_email": has_further_email,
        "mail_count": len(emails),
        "days_waiting": days_waiting,
        "confidence": confidence,
        "applied_at": applied_at.isoformat() if applied_at else None,
        "applied_date_inferred": stage != "applied",
        "latest_activity_at": latest_at.isoformat() if latest_at else None,
        "deadline": deadline.isoformat() if deadline else None,
        "days_left": days_left,
        "platform": group["platforms"][0] if group["platforms"] else "Email",
        "platforms": group["platforms"],
        "source_accounts": group["accounts"],
        "source_email": emails[0] if emails else None,
        "source_emails": emails[:20],
        "summary": _portfolio_summary(group, stage, response_status),
        "next_action": _next_action(
            stage,
            response_status,
            group["company"],
            role,
            days_waiting,
        ),
        "timeline": [
            {
                "at": item["occurred_at"].isoformat(),
                "stage": item["stage"],
                "title": item["subject"],
                "summary": item["summary"],
                "source_email_id": item["email_id"],
                "account_email": item["account_email"],
            }
            for item in reversed(signals)
            if item["occurred_at"]
        ][:24],
        "project": project,
        "opportunity_ids": group["opportunity_ids"],
        "archived": False,
    }


def _career_stage(lowered, subject, is_sent):
    career_context = any(
        cue in lowered
        for cue in (
            "application",
            "candidate",
            "position",
            "job",
            "intern",
            "role",
        )
    )
    if career_context and any(cue in lowered for cue in REJECTION_CUES):
        return "rejected"
    if any(cue in lowered for cue in OFFER_CUES):
        return "offer"
    if any(cue in lowered for cue in INTERVIEW_CUES):
        return "interview"
    if any(cue in lowered for cue in PROJECT_CUES):
        return "project"
    if any(cue in lowered for cue in ASSESSMENT_CUES):
        return "assessment"
    if any(cue in lowered for cue in SELECTION_CUES):
        return "shortlisted"
    if any(cue in lowered for cue in APPLICATION_CUES):
        return "applied"
    if is_sent and (
        subject.startswith("application for")
        or subject.startswith("job application")
        or subject.startswith("internship application")
    ):
        return "applied"
    return None


def _insight_backed_career_stage(email, text):
    sender = (email.sender or "").lower()
    career_sender = any(
        cue in sender
        for cue in (
            "recruit",
            "talent",
            "career",
            "jobs",
            "placement",
            "hr@",
        )
    )
    if not career_sender:
        return None
    if "interview" in text and any(
        cue in text
        for cue in ("recruit", "internship", "candidate", "prepare for the interview")
    ):
        return "interview"
    if "assessment" in text or "online test" in text:
        return "assessment"
    if "application" in text and any(
        cue in text
        for cue in ("candidate", "position", "internship", "job application")
    ):
        return "applied"
    return None


def _is_generic_career_broadcast(email, text, is_sent):
    if is_sent:
        return False
    sender = (email.sender or "").lower()
    college_broadcast = any(
        cue in sender
        for cue in (
            "placementoffice",
            "cdcinfo",
            "vitbhopal.ac.in",
            "vitstudent.ac.in",
        )
    )
    subject = (email.subject or "").lower()
    if "dear students" in text and "your application" not in text:
        return True
    broadcast_subject = any(
        cue in subject
        for cue in (
            "selection list",
            "selected candidates",
            "applied students",
            "registration - 2027",
            "registration 2027",
            "batch",
            "pre placement talk",
            "campus recruitment",
        )
    )
    if not college_broadcast and not broadcast_subject:
        return False
    personal = any(
        cue in text
        for cue in (
            "your application",
            "you have been shortlisted",
            "you are shortlisted",
            "you have qualified",
            "you are eligible",
            "invite you to interview",
        )
    )
    return not personal


def _has_specific_hackathon_signal(text):
    return any(
        cue in text
        for cue in (
            "hackathon",
            "buildathon",
            "datathon",
            "challenge",
            "competition",
            "registration confirmed",
            "registration details submitted",
            "days left to submit",
            "prototype submission",
            "submission successful",
            "selected for round",
        )
    ) or bool(re.search(r"\bgrid\s*\d", text, re.I))


def _career_confidence(text, stage, is_sent):
    confidence = 0.72
    if is_sent:
        confidence += 0.15
    if stage in SELECTED_STAGES or stage == "rejected":
        confidence += 0.1
    if "your application" in text or "thank you for applying" in text:
        confidence += 0.08
    return min(0.99, confidence)


def _career_evidence(text, stage, is_sent):
    if is_sent:
        return "Application message found in Sent mail."
    labels = {
        "applied": "Personal application confirmation found.",
        "shortlisted": "Personal next-round selection found.",
        "assessment": "Assessment or test invitation found.",
        "project": "Project or case-study round found.",
        "interview": "Interview invitation or schedule found.",
        "offer": "Offer wording found.",
        "rejected": "Application closure wording found.",
    }
    return labels.get(stage, "Career application evidence found.")


def _has_direct_personal_selection(text):
    return any(cue in text for cue in SELECTION_CUES + INTERVIEW_CUES)


def _has_direct_application_evidence(text, is_sent):
    return is_sent or any(
        cue in text
        for cue in (
            APPLICATION_CUES
            + SELECTION_CUES
            + ASSESSMENT_CUES
            + INTERVIEW_CUES
            + PROJECT_CUES
            + OFFER_CUES
            + REJECTION_CUES
        )
    )


def _application_group_key(signal, email):
    company = _normalize(signal["company"]) or "unknown"
    if company != "unknown company":
        return company
    role = _normalize(signal["role"]) or "application"
    if email.provider_thread_id:
        return f"{company}:thread:{email.account_id}:{email.provider_thread_id}"
    return f"{company}:{role}"


def _company(email, opportunity=None):
    subject = _clean(email.subject)
    for pattern in (
        r"\byour application to\s+.+?\s+at\s+([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60})$",
        r"\b(?:thanks|thank you) for applying to(?: the)?\s+.+?\s+at\s+([A-Za-z0-9][A-Za-z0-9 &.'-]{1,80})[!.]?$",
        r"\bupdate from\s+([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60}?)\s+on\b",
        r"\bapplication was sent to\s+([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60})",
        r"\bapplication was viewed by\s+([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60})",
        r"^([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60}?)\s*\|\|",
        r"\bapplication (?:at|with)\s+([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60})",
        r"\binterview (?:at|with)\s+([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60})",
        r"\boffer from\s+([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60})",
    ):
        match = re.search(pattern, subject, re.I)
        if match and _is_usable_company(match.group(1)):
            return _clean(match.group(1))[:120]
    if opportunity and _is_usable_company(opportunity.organization):
        return _clean(opportunity.organization)[:120]
    if email.insight:
        for value in _json_list(email.insight.companies_json):
            if _is_usable_company(value):
                return _clean(value)[:120]
    sender_name, address = parseaddr(email.sender or "")
    if _is_usable_company(sender_name):
        return _clean(sender_name)[:120]
    domain = address.split("@", 1)[-1].lower()
    label = domain.split(".")[0].replace("-", " ").title() if domain else ""
    return label if _is_usable_company(label) else "Unknown company"


def _is_usable_company(value):
    normalized = _normalize(value)
    if normalized in GENERIC_COMPANIES:
        return False
    return (
        bool(normalized)
        and len(normalized) >= 2
        and not any(
            phrase in normalized
            for phrase in (
                "no reply",
                "noreply",
                "recruiting team",
                "talent acquisition",
                "job alerts",
                "placement office",
            )
        )
    )


def _clean_company_name(value):
    clean = re.sub(
        r"\b(?:hiring|recruiting|talent acquisition)\s+team$",
        "",
        _clean(value),
        flags=re.I,
    ).strip(" -|")
    return clean[:120] or "Unknown company"


def _role(email, company, opportunity=None):
    if opportunity:
        current = _clean(opportunity.title)
        if current and not any(
            phrase in current.lower()
            for phrase in (
                "thank you for applying",
                "application received",
                "update from",
                "next steps",
                "follow-up",
                "your application to",
                "application was sent to",
                "application was viewed by",
                "application for",
                "thanks for applying to",
                "campus recruitment",
            )
        ):
            return current[:180]
    subject = re.sub(
        r"^(re|fwd|fw):\s*",
        "",
        _clean(email.subject),
        flags=re.I,
    )
    if "application was sent to" in subject.lower():
        return "Application"
    if "application was viewed by" in subject.lower():
        return "Application"
    if re.search(r"\b(?:thanks|thank you) for applying[!.]?$", subject, re.I):
        return "Application"
    patterns = (
        r"\b(?:thanks|thank you) for applying to(?: the)?\s+(.+?)\s+at\s+",
        r"\bapplication for\s+(.+?)(?:\s+(?:at|with)\s+|,| received|$)",
        r"\byour application for\s+(.+?)(?:\s+(?:at|with)\s+|,|$)",
        r"\bjob application:\s*(.+?)(?:\s+at\s+|,|$)",
        r"\bapplication to\s+(.+?)(?:\s+at\s+|,|$)",
        r"\binterview for\s+(.+?)(?:\s+(?:at|with)\s+|,|$)",
        r"\bassessment for\s+(.+?)(?:\s+(?:at|with)\s+|,|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, subject, re.I)
        if match:
            value = _clean(match.group(1)).strip(" :-")
            if value:
                return value.strip(" |:-")[:180]
    if company and subject.lower().startswith(company.lower()):
        subject = subject[len(company):].strip(" :-")
    subject = re.sub(
        r"\bCampus Recruitment\b",
        "",
        subject,
        flags=re.I,
    ).strip(" |:-")
    if "thank you for applying" in subject.lower():
        return "Application"
    return subject[:180] if len(subject) <= 90 else "Application"


def _platform(email, text):
    sender = (email.sender or "").lower()
    joined = f"{sender} {text}"
    rules = (
        ("LinkedIn", ("linkedin.com", "linkedin jobs")),
        ("Indeed", ("indeed.com",)),
        ("Glassdoor", ("glassdoor.com",)),
        ("Unstop", ("unstop.com",)),
        ("Hack2Skill", ("hack2skill.com",)),
        ("HackerEarth", ("hackerearth.com",)),
        ("Devfolio", ("devfolio.co",)),
        ("Greenhouse", ("greenhouse.io", "greenhouse")),
        ("Lever", ("lever.co",)),
        ("Workday", ("myworkday", "workday")),
        ("Keka", ("kekamail.com",)),
        ("SmartRecruiters", ("smartrecruiters.com",)),
        ("Workable", ("workablemail.com", "workable.com")),
        ("College placement", ("vitbhopal.ac.in", "placement office", "cdc info")),
    )
    for label, cues in rules:
        if any(cue in joined for cue in cues):
            return label
    if email.account and parseaddr(email.sender)[1].lower() == email.account.email.lower():
        return "Direct email"
    return "Company website"


def _response_status(stage, has_further_email, days_waiting):
    if stage in SELECTED_STAGES:
        return "selected"
    if stage == "rejected":
        return "rejected"
    if stage == "applied" and days_waiting >= NO_RESPONSE_DAYS:
        return "no_response"
    if stage == "applied" and not has_further_email:
        return "no_further_email"
    return "awaiting_response"


def _response_label(value):
    return {
        "selected": "Selected / next round",
        "rejected": "Closed / rejected",
        "no_response": f"No response for {NO_RESPONSE_DAYS}+ days",
        "no_further_email": "No further email yet",
        "awaiting_response": "Awaiting response",
    }.get(value, "Applied")


def _stage_label(stage):
    return {
        "assessment": "Assessment / test",
        "project": "Project submission",
        "interview": "Interview scheduled",
        "shortlisted": "Selected for next round",
        "offer": "Offer received",
        "rejected": "Closed / rejected",
        "applied": "Applied",
    }.get(stage, "Applied")


def _next_action(stage, response_status, company, role, days_waiting):
    if response_status == "no_response":
        return (
            f"No reply for {days_waiting} days. Check the portal or send one "
            f"short follow-up to {company}."
        )
    actions = {
        "applied": f"Watch {company} for an assessment or recruiter reply.",
        "shortlisted": f"Read the next-round instructions for {role} and reserve preparation time.",
        "assessment": "Open the assessment mail, verify the link, and complete the test before its deadline.",
        "project": "Link the project workspace and finish the highest-risk submission work first.",
        "interview": "Confirm the interview slot and prepare a project walkthrough plus role-specific questions.",
        "offer": "Review compensation, joining date, conditions, and the acceptance deadline.",
        "rejected": "Close the application and keep any useful feedback.",
    }
    return actions.get(stage, f"Review the latest application mail from {company}.")


def _portfolio_summary(group, stage, response_status):
    lines = []
    for value in reversed(group["summaries"]):
        clean = _clean(value)
        if clean and clean not in lines:
            lines.append(clean[:260])
        if len(lines) >= 2:
            break
    lines.append(
        f"Status: {_stage_label(stage)}. "
        f"Response: {_response_label(response_status)}."
    )
    lines.append(
        f"Grouped {len(group['emails'])} related email"
        f"{'' if len(group['emails']) == 1 else 's'} across "
        f"{len(group['accounts'])} account"
        f"{'' if len(group['accounts']) == 1 else 's'}."
    )
    return "\n".join(lines[:4])


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
    raw = (
        email.insight.summary
        if email.insight and email.insight.summary
        else email.snippet or email.body_text or email.subject
    )
    clean = _clean(raw)
    clean = re.split(
        r"\b(?:unsubscribe|manage preferences|view in browser)\b",
        clean,
        maxsplit=1,
        flags=re.I,
    )[0]
    sentences = [
        item.strip(" -")
        for item in re.split(r"(?<=[.!?])\s+", clean)
        if len(item.strip()) >= 12
    ]
    return " ".join(sentences[:2])[:500] or clean[:500]


def _hackathon_overview(emails, known_signals):
    groups = {}
    for email in emails:
        signal = known_signals.get(email.id) or classify_hackathon_email(email)
        if not signal:
            continue
        key = _normalize(signal["event"]) or f"hackathon-{email.id}"
        group = groups.setdefault(
            key,
            {
                "title": signal["event"],
                "signals": [],
                "platforms": [],
                "accounts": [],
            },
        )
        group["signals"].append(
            {
                **signal,
                "email_id": email.id,
                "subject": _clean(email.subject),
                "summary": _email_summary(email),
            }
        )
        _append_unique(group["platforms"], signal["platform"])
        if email.account:
            _append_unique(group["accounts"], email.account.email)

    items = []
    for key, group in groups.items():
        signals = sorted(
            group["signals"],
            key=lambda item: item["occurred_at"] or datetime.min,
        )
        latest = signals[-1]
        deadline = min(
            (
                item["deadline"]
                for item in signals
                if item["deadline"]
                and item["deadline"].date() >= date.today()
            ),
            default=None,
        )
        days_left = (
            (deadline.date() - date.today()).days
            if deadline
            else None
        )
        items.append(
            {
                "id": hashlib.sha1(key.encode("utf-8")).hexdigest()[:16],
                "title": group["title"],
                "stage": latest["stage"],
                "stage_label": latest["stage"].replace("_", " ").title(),
                "platforms": group["platforms"],
                "source_accounts": group["accounts"],
                "mail_count": len(signals),
                "deadline": deadline.isoformat() if deadline else None,
                "days_left": days_left,
                "latest_activity_at": (
                    latest["occurred_at"].isoformat()
                    if latest["occurred_at"]
                    else None
                ),
                "summary": latest["summary"],
            }
        )
    items.sort(
        key=lambda item: item["latest_activity_at"] or "",
        reverse=True,
    )
    progressed = {"applied", "building", "submitted", "selected", "won"}
    stats = {
        "total": len(items),
        "discovered": sum(item["stage"] == "discovered" for item in items),
        "applied": sum(item["stage"] in progressed for item in items),
        "building": sum(item["stage"] == "building" for item in items),
        "submitted": sum(item["stage"] == "submitted" for item in items),
        "selected": sum(item["stage"] in {"selected", "won"} for item in items),
        "won": sum(item["stage"] == "won" for item in items),
        "due_soon": sum(
            item["days_left"] is not None
            and 0 <= item["days_left"] <= 7
            for item in items
        ),
    }
    return {"stats": stats, "items": items[:40]}


def _hackathon_stage(text):
    if any(cue in text for cue in ("winner", "you have won", "your team has won")):
        return "won"
    if any(
        cue in text
        for cue in (
            "selected for",
            "shortlisted",
            "qualified for",
            "advanced to",
            "finalist",
            "eligible for the next round",
        )
    ):
        return "selected"
    if re.search(r"\bround\s*[2-9]\b", text) and any(
        cue in text for cue in ("assessment", "slot", "test credentials")
    ):
        return "selected"
    if any(
        cue in text
        for cue in (
            "submission successful",
            "successfully submitted",
            "prototype submitted",
            "submission received",
        )
    ):
        return "submitted"
    if any(
        cue in text
        for cue in (
            "days left to submit",
            "submit your",
            "build sprint",
            "prototype",
            "pitch deck",
        )
    ):
        return "building"
    if any(
        cue in text
        for cue in (
            "registration confirmed",
            "registration details submitted",
            "successfully registered",
            "you have registered",
            "application received",
        )
    ):
        return "applied"
    return "discovered"


def _hackathon_status_label(stage, subject):
    if stage == "selected":
        current_round = re.search(r"\bround\s*(\d+)\b", subject, re.I)
        if current_round:
            number = int(current_round.group(1))
            if "eligible for the next round" in subject.lower():
                number += 1
            return f"Selected for Round {number}"
        return "Selected for Next Round"
    return {
        "won": "Winner",
        "submitted": "Submitted",
        "building": "Build in progress",
        "applied": "Applied",
        "discovered": "Discovered",
    }.get(stage, stage.replace("_", " ").title())


def _hackathon_name(subject):
    clean = re.sub(
        r"^(re|fwd|fw):\s*",
        "",
        _clean(subject),
        flags=re.I,
    )
    grid = re.search(r"\b([A-Za-z0-9 &.'-]*GRiD\s*\d+(?:\.\d+)?)\b", clean, re.I)
    if grid:
        return _clean(grid.group(1)).strip(" -|")[:140]
    promptwars = re.search(r"\bPromptWars\b", clean, re.I)
    if promptwars:
        return "PromptWars"
    named_hackathon = re.findall(
        r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z0-9][A-Za-z0-9]*){0,4}\s+(?:Hackathon|Buildathon|Datathon)(?:\s+20\d{2})?)\b",
        clean,
    )
    if named_hackathon:
        return _clean(named_hackathon[-1])[:140]
    segments = [
        item.strip()
        for item in re.split(r"\s*[|:]\s*", clean)
        if item.strip()
    ]
    for segment in reversed(segments):
        if any(term in segment.lower() for term in HACKATHON_TERMS[:3]):
            clean = segment
            break
    patterns = (
        r"\b(?:your\s+)?([A-Za-z0-9][A-Za-z0-9 &.'-]{0,60}?(?:Hackathon|Buildathon|Datathon)(?:\s+20\d{2})?)\b",
        r"\b([A-Za-z0-9][A-Za-z0-9 &.'-]{1,60}?\s+Challenge(?:\s+20\d{2})?)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, clean, re.I)
        if match:
            value = re.sub(
                r"^\d+\s+days?\s+left\s+to\s+(?:submit\s+)?",
                "",
                match.group(1),
                flags=re.I,
            )
            value = re.sub(
                r"^(?:submit\s+)?your\s+",
                "",
                value,
                flags=re.I,
            )
            value = re.sub(
                r"^(?:lock in|submit|join|enter)\s+",
                "",
                value,
                flags=re.I,
            )
            return _clean(value)[:140]
    return clean[:140] or "Hackathon update"


def _is_hackathon_text(text):
    return any(term in text for term in HACKATHON_TERMS) or bool(
        re.search(r"\bgrid\s*\d", text, re.I)
    )


def _mail_category_counts(emails, career_signals, hackathon_signals):
    counts = Counter()
    for email in emails:
        if email.id in career_signals:
            counts["Applications"] += 1
            continue
        if email.id in hackathon_signals:
            counts["Hackathons"] += 1
            continue
        sender = (email.sender or "").lower()
        labels = set(_json_list(email.labels_json))
        category = email.insight.category if email.insight else "general"
        if "github.com" in sender:
            counts["GitHub"] += 1
        elif category in {"learning", "assignment"}:
            counts["Learning"] += 1
        elif category == "meeting":
            counts["Meetings"] += 1
        elif category == "finance":
            counts["Finance"] += 1
        elif "CATEGORY_PROMOTIONS" in labels:
            counts["Promotions"] += 1
        else:
            counts["Other inbox"] += 1
    total = max(1, len(emails))
    return [
        {
            "label": label,
            "count": count,
            "percent": round(count / total * 100),
        }
        for label, count in counts.most_common()
    ]


def _status_counts(items):
    counts = Counter(item["response_status"] for item in items)
    return [
        {
            "key": key,
            "label": _response_label(key),
            "count": counts.get(key, 0),
        }
        for key in (
            "selected",
            "awaiting_response",
            "no_further_email",
            "no_response",
            "rejected",
        )
    ]


def _opportunity_deadline(opportunity):
    return opportunity.deadline if opportunity else None


def _email_deadline(email):
    deadlines = [
        task.due_at
        for task in email.tasks
        if task.due_at
    ]
    if deadlines:
        return min(deadlines)
    text = _email_text(email).lower()
    anchor = email.sent_at or email.created_at or datetime.utcnow()
    remaining = re.search(r"\b(\d{1,2})\s+days?\s+left\b", text)
    if remaining:
        return anchor + timedelta(days=int(remaining.group(1)))
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", text)
    if numeric:
        day, month, year = map(int, numeric.groups())
        try:
            return datetime(year, month, day, 18, 0)
        except ValueError:
            return None
    return None


def _project_candidates():
    return (
        LifeItem.query.filter(
            (LifeItem.category == "project")
            | (
                (LifeItem.repository.isnot(None))
                & (LifeItem.repository != "")
            )
            | (
                (LifeItem.working_directory.isnot(None))
                & (LifeItem.working_directory != "")
            )
        )
        .order_by(LifeItem.updated_at.desc())
        .all()
    )


def _linked_project(company, roles, projects):
    terms = set(
        _normalize(f"{company} {' '.join(roles)}").split()
    ) - {
        "intern",
        "internship",
        "engineer",
        "developer",
        "application",
    }
    best = None
    best_score = 0
    for item in projects:
        haystack = set(
            _normalize(
                f"{item.title} {item.description or ''} {item.tags_json or ''}"
            ).split()
        )
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


def _dedupe_emails(values):
    output = []
    seen = set()
    for item in sorted(
        values,
        key=lambda value: value.get("received_at") or "",
        reverse=True,
    ):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        output.append(item)
    return output


def _application_sort_key(item):
    return item["latest_activity_at"] or item["applied_at"] or ""


def _email_text(email):
    return _clean(
        f"{email.sender or ''} {email.subject or ''} "
        f"{email.snippet or ''} {email.body_text or ''}"
    )


def _clean(value):
    text = html.unescape(str(value or ""))
    text = re.sub(
        r"[\u00ad\u034f\u061c\u115f-\u1160\u17b4-\u17b5"
        r"\u180b-\u180f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]",
        "",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


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
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value or "").lower(),
    ).strip()
