import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parseaddr


CATEGORY_LABELS = {
    "internship": "Applications",
    "career": "Job discovery",
    "hackathon": "Hackathons",
    "college": "College",
    "github": "GitHub",
    "security": "Security",
    "meeting": "Meetings",
    "assignment": "Assignments",
    "reminder": "Reminders",
    "finance": "Finance",
    "travel": "Travel",
    "shopping": "Shopping",
    "learning": "Learning",
    "social": "Social",
    "newsletter": "Newsletters",
    "personal": "Personal",
    "general": "Other",
}


@dataclass(frozen=True)
class EmailTriage:
    category: str
    priority: str
    urgency: str
    attention_score: int
    priority_reason: str
    is_actionable: bool
    signals: tuple[str, ...] = ()


def classify_email_category(sender="", subject="", body=""):
    """Classify by the strongest source signal, keeping generic mail out of action views."""
    address = parseaddr(sender or "")[1].lower()
    subject_text = _clean(subject)
    text = _clean(f"{subject} {body} {address}")[:5000]

    if _has(
        text,
        "security alert",
        "suspicious sign-in",
        "password reset",
        "unused oauth",
        "oauth clients",
        "vulnerability alert",
        "compromised account",
        "verify your identity",
    ):
        return "security"
    if "github.com" in address or re.search(r"^\[[\w.-]+/[\w.-]+\]", subject or ""):
        return "github"
    if _has(address, "vitbhopal.ac.in") or _has(
        text,
        "tcs benchmark assessment",
        "pat class",
        "pat exam",
        "cdc assessment portal",
        "campus placement",
        "placement office",
    ):
        return "college"
    if _has(
        text,
        "hackathon",
        "buildathon",
        "datathon",
        "devfolio",
        "hack2skill",
        "devpost",
        "promptwars",
    ) or (
        _has(address, "unstop.com", "hackerearth.com")
        and _has(text, "challenge", "competition", "submission", "registration")
    ):
        return "hackathon"

    # Application status is personal only when the message talks about the user's
    # application, interview, assessment, or offer. Job-alert newsletters stay in
    # Career even when they mention interviews or applying.
    if _is_personal_application(text):
        return "internship"
    if _has(address, "match.indeed.com", "glassdoor.com", "linkedin.com") and _has(
        text,
        "job alert",
        "jobs in",
        "jobs for you",
        "apply now",
        "recommended job",
        "new jobs",
    ):
        return "career"
    if _has(
        subject_text,
        "calendar invite",
        "meeting invitation",
        "meeting scheduled",
        "interview schedule",
        "join meeting",
        "event invitation",
    ):
        return "meeting"
    if _has(text, "assignment due", "homework", "coursework", "submit assignment", "quiz due", "lab submission"):
        return "assignment"
    if _has(text, "payment received", "payment due", "invoice", "bank statement", "refund", "tax document", "salary credited"):
        return "finance"
    if _has(text, "flight booking", "boarding pass", "hotel booking", "travel itinerary", "train ticket"):
        return "travel"
    if _has(text, "order shipped", "out for delivery", "order delivered", "tracking number", "purchase receipt"):
        return "shopping"
    if _has(text, "course enrolled", "new lesson", "learning path", "workshop registration", "webinar registration", "course completion"):
        return "learning"
    if _has(address, "messages-noreply@linkedin.com", "facebookmail.com", "instagram.com") or _has(
        subject_text,
        "view your post",
        "new connection",
        "mentioned you",
        "new skill available",
    ):
        return "social"
    if _has(text, "reminder:", "don't forget", "do not forget", "following up", "friendly reminder"):
        return "reminder"
    if _has(text, "unsubscribe", "manage preferences", "view in browser", "email preferences"):
        return "newsletter"
    if _has(text, "family", "birthday", "personal appointment"):
        return "personal"
    return "general"


def triage_email(
    *,
    sender="",
    subject="",
    body="",
    preferred_category="",
    labels=None,
    is_unread=False,
    has_deadline=False,
    has_action=False,
    has_meeting=False,
    sent_at=None,
):
    """Return a stable, explainable attention score for the local inbox.

    The score is intentionally not a probability. It ranks attention using a
    small set of explainable signals, with bulk mail caps so newsletters and job
    alerts cannot outrank a personal deadline by accident.
    """
    text = _decision_text(subject, body)
    address = parseaddr(sender or "")[1].lower()
    detected = classify_email_category(sender, subject, body)
    category = detected if detected != "general" else _valid_category(preferred_category)
    labels = {str(value).upper() for value in labels or []}
    reasons = []
    signals = []
    score = {
        "security": 50,
        "github": 30,
        "college": 34,
        "internship": 36,
        "hackathon": 36,
        "meeting": 34,
        "assignment": 34,
        "reminder": 28,
        "finance": 18,
        "learning": 18,
        "travel": 16,
        "shopping": 12,
        "career": 12,
        "personal": 16,
        "social": 8,
        "newsletter": 5,
        "general": 14,
    }[category]

    action_signal = bool(has_action or detect_action_signal(subject, body))
    deadline_signal = bool(has_deadline or detect_deadline_signal(subject, body))
    failure_signal = category == "github" and _has(
        text,
        "run failed",
        "workflow failed",
        "checks have failed",
        "build failed",
        "deployment failed",
        "security vulnerability",
    )
    immediate_signal = _has(
        text,
        "urgent",
        "asap",
        "due today",
        "today at",
        "hours left",
        "24 hours left",
        "ends today",
        "closing today",
        "last day",
    )
    positive_outcome_signal = _has(
        text,
        "shortlisted",
        "selected for",
        "qualified for",
        "offer letter",
        "invite you to interview",
        "interview scheduled",
    )
    status_signal = _has(
        text,
        "application received",
        "thank you for applying",
        "not moving forward",
        "not selected",
        "rejected",
    )
    bulk_signal = category in {"career", "newsletter", "social", "shopping"} or (
        category in {"general", "finance", "travel", "learning", "personal"}
        and _has(address, "noreply", "no-reply", "notifications")
    )

    # Generic job-alert mail may contain "apply" and "interview" but does not
    # represent a commitment unless it is addressed to an existing application.
    if category == "career" and not _has(
        text,
        "your application",
        "your interview",
        "your assessment",
        "you have been shortlisted",
        "you have been selected",
    ):
        action_signal = False
        positive_outcome_signal = False

    if action_signal:
        score += 24
        signals.append("action")
        reasons.append("A direct action is requested")
    if failure_signal:
        score += 30
        signals.append("failure")
        reasons.append("A repository check or workflow failed")
    if deadline_signal:
        score += 22
        signals.append("deadline")
        reasons.append("A deadline or due date was detected")
    if immediate_signal:
        score += 18
        signals.append("immediate")
        reasons.append("The timing is immediate")
    if has_meeting:
        score += 14
        signals.append("meeting")
        reasons.append("A scheduled event needs preparation")
    if positive_outcome_signal:
        score += 14
        signals.append("outcome")
        reasons.append("A selection, interview, or offer changed")
    if status_signal:
        signals.append("status")
    if "IMPORTANT" in labels:
        score += 8
        signals.append("important")
        reasons.append("Gmail marks it important")
    if is_unread and (action_signal or deadline_signal or positive_outcome_signal or failure_signal):
        score += 4
        signals.append("unread")

    # A marketing or automated message is allowed to rise only when it contains
    # an explicit personal deadline/outcome. This is the key false-positive guard.
    informational_bulk = bulk_signal and not (
        action_signal or deadline_signal or immediate_signal or positive_outcome_signal
    )
    if informational_bulk:
        score = min(score, 24)
        reasons = ["Informational or bulk mail with no direct action"]
    if category == "general" and not (action_signal or deadline_signal or positive_outcome_signal):
        score = min(score, 22)
    if category == "internship" and status_signal and not (
        action_signal or deadline_signal or positive_outcome_signal
    ):
        score = min(score, 48)

    stale_deadline = _older_than(sent_at, days=10) and (deadline_signal or immediate_signal)
    if stale_deadline and category not in {"security", "github"}:
        score = min(score, 48)
        immediate_signal = False
        reasons.insert(0, "This older message may refer to an expired deadline")
        signals.append("stale")

    score = max(0, min(100, score))
    actionable = bool(
        action_signal
        or deadline_signal
        or failure_signal
        or positive_outcome_signal
        or category in {"security", "meeting", "assignment"}
        or (category in {"internship", "hackathon", "college"} and score >= 55)
    ) and not informational_bulk

    if score >= 70 and immediate_signal and actionable:
        priority = "urgent"
    elif not stale_deadline and (score >= 50 or (actionable and deadline_signal)):
        priority = "high"
    elif score >= 28:
        priority = "normal"
    else:
        priority = "low"

    if stale_deadline and category not in {"security", "github"}:
        urgency = "normal"
    elif immediate_signal and actionable:
        urgency = "urgent"
    elif deadline_signal or positive_outcome_signal or (actionable and score >= 55):
        urgency = "high"
    elif informational_bulk:
        urgency = "low"
    else:
        urgency = "normal"

    if not reasons:
        reasons.append(
            "Useful context, but no immediate action was detected"
            if score >= 25
            else "Low-priority informational mail"
        )
    return EmailTriage(
        category=category,
        priority=priority,
        urgency=urgency,
        attention_score=score,
        priority_reason=". ".join(dict.fromkeys(reasons[:3])) + ".",
        is_actionable=actionable,
        signals=tuple(dict.fromkeys(signals)),
    )


def detect_action_signal(subject="", body=""):
    text = _decision_text(subject, body)
    return bool(
        re.search(
            r"\b(?:action (?:required|advised)|review requested|changes requested|"
            r"report immediately|incomplete registration|"
            r"(?:can|could|would) you\b|"
            r"please (?:confirm|complete|finish|submit|upload|send|review|register|respond|reply|attend|fill)|"
            r"kindly (?:confirm|complete|submit|upload|send|register|respond|report)|"
            r"you (?:must|need to|are required to)|"
            r"complete (?:your|the)\b|submit (?:your|the|by)\b|register (?:by|before)\b)",
            text,
        )
    )


def detect_deadline_signal(subject="", body=""):
    text = _decision_text(subject, body)
    if _has(text, "days left", "hours left", "due today", "due tomorrow", "final day", "last day"):
        return True
    return bool(
        re.search(
            r"\b(?:deadline|due|submit|complete|register|respond|closing|ends)\b.{0,45}"
            r"\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)\b",
            text,
        )
    )


def _is_personal_application(text):
    if _has(text, "job alert", "jobs for you", "recommended job", "new jobs"):
        return False
    return _has(
        text,
        "thank you for applying",
        "application received",
        "application submitted",
        "your application for",
        "your application has",
        "not moving forward with your application",
        "not moving forward",
        "not selected",
        "selected for the next round",
        "shortlisted",
        "invite you to interview",
        "interview scheduled",
        "interview is scheduled",
        "interview invite",
        "schedule your interview",
        "internship interview",
        "assessment for your application",
        "offer letter",
        "online assessment link",
    )


def _valid_category(value):
    category = str(value or "general").lower().strip()
    return category if category in CATEGORY_LABELS else "general"


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _decision_text(subject, body):
    body_text = str(body or "")
    # Reply chains and forwarded history are useful context, but should not make
    # an old request look like a new action addressed to the user.
    body_text = re.split(
        r"(?:\r?\n){1,2}(?:on .{0,120} wrote:|[- ]{5,}forwarded message[- ]{5,}|from:\s)",
        body_text,
        maxsplit=1,
        flags=re.I,
    )[0]
    return _clean(f"{subject} {body_text[:2200]}")


def _has(text, *phrases):
    return any(phrase in text for phrase in phrases)


def _older_than(value, *, days):
    if not isinstance(value, datetime):
        return False
    now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
    return value <= now - timedelta(days=days)
