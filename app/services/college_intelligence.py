import html
import re
from datetime import date, datetime, timedelta

from app.models import EmailMessage


PAT_PATTERN = re.compile(r"\bPAT\b|placement aptitude training|professional aptitude training", re.I)
CLASS_CUES = (
    "class",
    "training",
    "session",
    "exam",
    "test",
    "assessment",
    "attendance",
    "remedial",
    "group a",
    "group b",
    "reporting time",
)
OPPORTUNITY_CUES = ("internship registration", "offer registration", "job registration", "date of visit")
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
BRING_ITEMS = {
    "laptop": ("laptop",),
    "notebook": ("notebook", "notepad"),
    "pen": (" pen ", "pens"),
    "pencil": ("pencil",),
    "college ID card": ("id card", "college id"),
    "resume / CV": ("resume", " cv "),
    "calculator": ("calculator",),
    "headphones": ("headphones", "earphones"),
    "charger": ("charger",),
    "10th marksheet": ("10th marksheet", "10th mark sheet"),
    "12th marksheet": ("12th marksheet", "12th mark sheet"),
    "UG marksheet": ("ug marksheet", "ug mark sheet"),
    "passport photo": ("passport photo", "passport size photo"),
    "rough sheets": ("rough sheets", "rough pages"),
}


def pat_college_summary(today=None, limit=40):
    today = today or date.today()
    candidates = EmailMessage.query.order_by(EmailMessage.sent_at.desc()).limit(100).all()
    messages = [email for email in candidates if _is_pat_college_notice(email)][:limit]
    updates = [_serialize_pat_email(email, today) for email in messages]
    today_updates = [item for item in updates if item["event_date"] == today.isoformat()]
    active_today = [item for item in today_updates if item["status"] != "cancelled"]
    cancelled_today = [item for item in today_updates if item["status"] == "cancelled"]
    upcoming = sorted(
        [item for item in updates if item["event_date"] and item["event_date"] >= today.isoformat() and item["status"] != "cancelled"],
        key=lambda item: (item["event_date"], item["timestamp"] or ""),
    )
    next_event = upcoming[0] if upcoming else None
    primary = (active_today or cancelled_today or ([next_event] if next_event else []) or updates or [None])[0]
    preparation_updates = active_today[:5] or upcoming[:5]
    bring = _unique(item for update in preparation_updates for item in update["bring"])
    instructions = _unique(item for update in preparation_updates for item in update["instructions"])
    if active_today:
        headline = "PAT class is scheduled today"
        status = "scheduled"
    elif cancelled_today:
        headline = "Today's PAT class is cancelled"
        status = "cancelled"
    elif next_event:
        event_day = date.fromisoformat(next_event["event_date"])
        days_left = (event_day - today).days
        relative = "tomorrow" if days_left == 1 else f"in {days_left} days"
        headline = f"Next PAT event is {event_day.strftime('%A, %d %b')} ({relative})"
        status = "upcoming"
    elif updates:
        headline = "No PAT class found for today"
        status = "no_class_found"
    else:
        headline = "No PAT mail has been detected yet"
        status = "not_connected"
    return {
        "date": today.isoformat(),
        "status": status,
        "has_class_today": bool(active_today),
        "headline": headline,
        "time": primary["time"] if primary else "",
        "location": primary["location"] if primary else "",
        "bring": bring,
        "instructions": instructions,
        "latest_subject": primary["subject"] if primary else "",
        "latest_summary": primary["summary"] if primary else "Connect Gmail in AiOS and run Sync to scan PAT notices.",
        "emails_scanned": len(candidates),
        "next_event": next_event,
        "next_event_days": (date.fromisoformat(next_event["event_date"]) - today).days if next_event else None,
        "updates": updates[:12],
    }


def _serialize_pat_email(email, today):
    text = _email_text(email)
    clean_text = _without_quoted_headers(text)
    lowered = f" {clean_text.lower()} "
    cancelled = any(term in lowered for term in ("cancelled", "canceled", "no pat class", "class is postponed"))
    anchor = email.sent_at or datetime.utcnow()
    event_date = _event_date(email.subject or "", anchor, today) or _event_date(clean_text, anchor, today)
    return {
        "email_id": email.id,
        "subject": email.subject,
        "sender": email.sender or "",
        "timestamp": email.sent_at.isoformat() if email.sent_at else None,
        "event_date": event_date.isoformat() if event_date else None,
        "status": "cancelled" if cancelled else "scheduled",
        "time": _extract_time(clean_text),
        "location": _extract_location(clean_text),
        "bring": [label for label, terms in BRING_ITEMS.items() if any(term in lowered for term in terms)],
        "instructions": _extract_instructions(clean_text),
        "summary": _pat_summary(email, clean_text, event_date),
    }


def _email_text(email):
    return html.unescape(f"{email.subject or ''}\n{email.snippet or ''}\n{email.body_text or ''}")


def _is_pat_college_notice(email):
    text = _email_text(email)
    if not PAT_PATTERN.search(text):
        return False
    subject = (email.subject or "").lower()
    clean_text = _without_quoted_headers(text).lower()
    registration_mail = "registration" in subject and any(
        cue in subject for cue in ("internship", "offer", "company", "batch", "recruitment")
    )
    if registration_mail or any(cue in subject for cue in OPPORTUNITY_CUES):
        return False
    return any(cue in clean_text for cue in CLASS_CUES)


def _without_quoted_headers(text):
    text = html.unescape(text or "")
    current_message = re.split(
        r"(?:^|\n)\s*On\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?.{0,600}?(?:wrote:|$)",
        text,
        maxsplit=1,
        flags=re.I | re.S,
    )[0]
    lines = []
    for line in current_message.splitlines():
        if re.match(r"^\s*(from|sent|date|subject|to|cc):\s", line, re.I):
            continue
        lines.append(line)
    return "\n".join(lines)


def _pat_summary(email, clean_text, event_date):
    text = re.sub(r"\s+", " ", clean_text).strip()
    text = re.split(r"\b(?:unsubscribe|manage preferences|view in browser)\b", text, maxsplit=1, flags=re.I)[0]
    sentences = [part.strip(" -") for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) >= 18]
    lines = [sentence[:220] for sentence in sentences[:2]]
    if not lines:
        lines.append((email.subject or "PAT notice")[:220])
    if len(lines) < 2:
        lines.append("This notice was detected from the latest locally synced PAT mail.")
    if event_date:
        lines.append(f"Event date: {event_date.strftime('%A, %d %b %Y')}.")
    else:
        lines.append("Event date was not stated clearly in the mail.")
    lines.append("Action: review the preparation details and latest timeline update below.")
    return "\n".join(lines[:4])


def _event_date(text, anchor, today):
    lowered = text.lower()
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", text)
    if numeric:
        day, month, year = map(int, numeric.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            pass
    named = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+(\d{4}))?\b",
        lowered,
    )
    if named:
        day = int(named.group(1))
        month = MONTHS[named.group(2)]
        year = int(named.group(3) or anchor.year)
        try:
            return date(year, month, day)
        except ValueError:
            pass
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for index, weekday in enumerate(weekdays):
        if re.search(rf"\b{weekday}\b", lowered):
            return anchor.date() + timedelta(days=(index - anchor.weekday()) % 7)
    if re.search(r"\btomorrow\b", lowered):
        return anchor.date() + timedelta(days=1)
    if re.search(r"\btoday\b", lowered):
        return anchor.date()
    return None


def _extract_time(text):
    match = re.search(
        r"\b(?:at|from|time|reporting time)[:\s-]*((?:[01]?\d|2[0-3])(?:[:.]\d{2})?\s*(?:am|pm))\b",
        text,
        re.I,
    )
    return match.group(1).replace(".", ":").strip() if match else ""


def _extract_location(text):
    match = re.search(r"\b(?:venue|room|location|lab|auditorium|building|campus)[:\s-]+([^\n.;]{1,80})", text, re.I)
    if not match:
        return ""
    location = match.group(1).strip()
    if re.fullmatch(r"(?:[01]?\d|2[0-3])(?::\d{2})?\s*(?:am|pm)", location, re.I):
        return ""
    return location


def _extract_instructions(text):
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    signals = ("bring", "carry", "report", "attendance", "mandatory", "wear", "venue", "submit")
    return _unique(sentence.strip()[:220] for sentence in sentences if any(signal in sentence.lower() for signal in signals))[:8]


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))
