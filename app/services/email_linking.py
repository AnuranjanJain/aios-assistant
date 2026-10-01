"""Local, explainable relationships between messages in the mail portfolio."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from email.utils import parseaddr

from app.models import EmailMessage, EmailMessageLink, db
from app.services.email_scope import EMAIL_PORTFOLIO_LIMIT, latest_emails_combined


_STOP_WORDS = {
    "about", "after", "alert", "application", "available", "from", "have",
    "hello", "important", "information", "mail", "message", "notification",
    "please", "regarding", "reply", "request", "response", "the", "this",
    "update", "your",
}
_RELATION_WORDS = {
    "reminder": ("reminder", "don't forget", "do not forget", "last chance"),
    "join_notification": ("join meeting", "google meet", "zoom", "teams", "calendar invite"),
    "update": ("status update", "next round", "selection list", "result", "updated"),
    "reply": ("in reply to", "following up", "as discussed", "thanks for your reply"),
}


def relink_recent_emails(limit=EMAIL_PORTFOLIO_LIMIT):
    """Link strong matches and persist an explicit status for every insight.

    A message is not linked merely because it shares a sender. Matching needs
    a Gmail thread, a stable subject, or several meaningful subject tokens plus
    a compatible time/domain signal. Ambiguous matches become ``needs_review``;
    everything else is explicitly ``unrelated``.
    """
    emails = [item for item in latest_emails_combined(limit) if item.id is not None]
    if not emails:
        return {"linked": 0, "unrelated": 0, "needs_review": 0, "processed": 0}

    email_ids = [item.id for item in emails]
    EmailMessageLink.query.filter(
        db.or_(
            EmailMessageLink.source_email_id.in_(email_ids),
            EmailMessageLink.target_email_id.in_(email_ids),
        )
    ).delete(synchronize_session=False)

    emails_by_id = {item.id: item for item in emails}
    details = {item.id: _message_details(item) for item in emails}
    subject_index = defaultdict(set)
    token_index = defaultdict(set)
    thread_index = defaultdict(set)
    domain_index = defaultdict(set)
    for item in emails:
        info = details[item.id]
        if info["subject_key"]:
            subject_index[info["subject_key"]].add(item.id)
        for token in info["tokens"]:
            token_index[token].add(item.id)
        if info["thread_key"]:
            thread_index[info["thread_key"]].add(item.id)
        if info["domain"]:
            domain_index[info["domain"]].add(item.id)

    statuses = {item.id: {"status": "unrelated", "hint": None, "ids": set()} for item in emails}
    linked = 0
    review = 0
    for item in emails:
        info = details[item.id]
        candidates = set()
        if info["thread_key"]:
            candidates.update(thread_index[info["thread_key"]])
        if info["subject_key"]:
            candidates.update(subject_index[info["subject_key"]])
        for token in info["tokens"]:
            candidates.update(token_index[token])
        if info["domain"]:
            candidates.update(domain_index[info["domain"]])
        candidates.discard(item.id)

        best = None
        for candidate_id in candidates:
            if candidate_id <= item.id:
                continue
            candidate = emails_by_id.get(candidate_id)
            if candidate is None:
                continue
            score, relation, reason = _relationship_score(item, candidate, info, details[candidate_id])
            if score < 0.5:
                continue
            candidate_result = (score, candidate, relation, reason)
            if best is None or candidate_result[0] > best[0]:
                best = candidate_result

        if best is None:
            continue
        score, candidate, relation, reason = best
        older, newer = _ordered_pair(item, candidate)
        if score >= 0.72:
            _upsert_link(older, newer, relation, score, reason)
            statuses[item.id]["status"] = "related"
            statuses[candidate.id]["status"] = "related"
            statuses[item.id]["hint"] = relation
            statuses[candidate.id]["hint"] = relation
            statuses[item.id]["ids"].add(candidate.id)
            statuses[candidate.id]["ids"].add(item.id)
            linked += 1
        else:
            for row_id in (item.id, candidate.id):
                if statuses[row_id]["status"] != "related":
                    statuses[row_id]["status"] = "needs_review"
                    statuses[row_id]["hint"] = relation
            review += 1

    for item in emails:
        insight = item.insight
        if insight is None:
            continue
        state = statuses[item.id]
        insight.relationship_status = state["status"]
        insight.relationship_hint = state["hint"]
        insight.related_email_ids_json = json.dumps(sorted(state["ids"]))
        db.session.add(insight)
    db.session.commit()
    return {
        "linked": linked,
        "unrelated": sum(state["status"] == "unrelated" for state in statuses.values()),
        "needs_review": review,
        "processed": len(emails),
    }


def _message_details(email):
    subject_key = _normalize_subject(email.subject)
    tokens = _meaningful_tokens(subject_key)
    address = parseaddr(email.sender or "")[1].lower()
    domain = address.rsplit("@", 1)[-1] if "@" in address else ""
    thread_key = f"{email.account_id}:{email.provider_thread_id}" if email.provider_thread_id else ""
    text = f"{email.subject or ''} {email.snippet or ''}".lower()
    return {
        "subject_key": subject_key,
        "tokens": tokens,
        "domain": domain,
        "thread_key": thread_key,
        "text": text,
        "date": email.sent_at or email.created_at,
    }


def _relationship_score(left, right, left_info, right_info):
    if left_info["thread_key"] and left_info["thread_key"] == right_info["thread_key"]:
        return 1.0, "same_thread", "Gmail grouped these messages in the same thread."

    left_tokens = set(left_info["tokens"])
    right_tokens = set(right_info["tokens"])
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    subject_match = bool(left_info["subject_key"] and left_info["subject_key"] == right_info["subject_key"])
    days = _days_between(left_info["date"], right_info["date"])
    same_domain = bool(left_info["domain"] and left_info["domain"] == right_info["domain"])
    application_signal = _has_application_language(left_info["text"] + " " + right_info["text"])

    # Repeated digest and notification subjects are common. Once they fall
    # outside the recent window, only explicit application context is strong
    # enough to connect them without a Gmail thread id.
    if days > 120 and not application_signal:
        return 0.0, "unrelated", "The matching subject is outside the local relationship window."

    score = 0.0
    if subject_match and overlap >= 2:
        score = 0.82
    elif overlap >= 2:
        score = 0.42 + min(0.25, overlap * 0.08)
    if same_domain:
        score += 0.08
    if application_signal:
        score += 0.08
    if union and overlap / union >= 0.55:
        score += 0.08
    if days <= 14:
        score += 0.06
    elif days > 120:
        score -= 0.18
    if score < 0.5:
        return score, "unrelated", "The messages do not share enough stable context."
    relation = _relation_type(left_info["text"], right_info["text"], subject_match)
    reason = {
        "reply": "The subject and reply language indicate a continuing conversation.",
        "reminder": "The messages share context and one is phrased as a reminder.",
        "update": "The messages share context and one contains a status or result update.",
        "join_notification": "The messages share context and one contains a meeting or join notice.",
        "application_update": "The messages share application context across an update stage.",
        "follow_up": "The messages share a meaningful subject and time window.",
    }.get(relation, "The messages share a stable local context.")
    return min(0.99, max(0.0, score)), relation, reason


def _upsert_link(source, target, relation, confidence, reason):
    row = EmailMessageLink.query.filter_by(
        source_email_id=source.id,
        target_email_id=target.id,
        relation_type=relation,
    ).first()
    if row is None:
        row = EmailMessageLink(
            source_email_id=source.id,
            target_email_id=target.id,
            relation_type=relation,
        )
    row.confidence = round(float(confidence), 3)
    row.reason = reason
    db.session.add(row)


def _ordered_pair(left, right):
    left_date = left.sent_at or left.created_at or datetime.min
    right_date = right.sent_at or right.created_at or datetime.min
    if (left_date, left.id) <= (right_date, right.id):
        return left, right
    return right, left


def _normalize_subject(value):
    text = re.sub(r"^(?:(?:re|fw|fwd)\s*:\s*)+", "", str(value or ""), flags=re.I)
    text = re.sub(r"\[[^\]]+\]", " ", text)
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def _meaningful_tokens(value):
    return tuple(token for token in value.split() if len(token) >= 4 and token not in _STOP_WORDS)[:18]


def _relation_type(left_text, right_text, subject_match):
    text = f"{left_text} {right_text}"
    if subject_match and (
        re.match(r"^\s*re\s*:", left_text, re.I)
        or re.match(r"^\s*re\s*:", right_text, re.I)
    ):
        return "reply"
    for relation, words in _RELATION_WORDS.items():
        if any(word in text for word in words):
            return relation
    if _has_application_language(text):
        return "application_update"
    return "follow_up"


def _has_application_language(text):
    return any(
        value in text
        for value in (
            "application", "applied", "assessment", "interview", "shortlisted",
            "selected", "next round", "offer", "recruitment",
        )
    )


def _days_between(left, right):
    if left is None or right is None:
        return 999
    return abs((left - right).total_seconds()) / 86400
