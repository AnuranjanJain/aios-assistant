"""Durable application lifecycle and evidence linking."""

from __future__ import annotations

import re
from datetime import datetime

from app.models import ApplicationDecision, ApplicationEvidence, ApplicationRecord, db


APPLICATION_STATUSES = frozenset(
    {
        "to_apply",
        "applied",
        "waiting",
        "assessment",
        "interview",
        "offer",
        "on_hold",
        "skipped",
        "rejected",
        "closed",
    }
)


def normalize_application_value(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def upsert_application_evidence(email, signal: dict) -> ApplicationRecord:
    """Link one email to a durable record without merging different roles."""

    company = str(signal.get("company") or "Unknown company").strip()
    role = str(signal.get("role") or "").strip()
    normalized_company = normalize_application_value(company) or "unknown company"
    normalized_role = normalize_application_value(role) or None
    requisition_id = str(signal.get("requisition_id") or "").strip() or None
    application_url = str(signal.get("application_url") or "").strip() or None

    record = _find_record(
        normalized_company,
        normalized_role,
        requisition_id,
        application_url,
    )
    if record is None:
        source_key = _source_key(normalized_company, normalized_role, requisition_id, application_url)
        record = ApplicationRecord(
            source_key=source_key,
            company=company,
            normalized_company=normalized_company,
            role=role or None,
            normalized_role=normalized_role,
            requisition_id=requisition_id,
            application_url=application_url,
            status="to_apply",
        )
        db.session.add(record)
        db.session.flush()

    existing = ApplicationEvidence.query.filter_by(email_id=email.id).one_or_none()
    if existing is None:
        evidence = ApplicationEvidence(
            application=record,
            email=email,
            kind=str(signal.get("kind") or "opening"),
            source_account=(email.account.email if email.account else None),
            application_url=application_url,
            extracted_deadline=signal.get("deadline"),
            confidence=float(signal.get("confidence") or 0.0),
            summary=str(signal.get("summary") or "").strip() or None,
            occurred_at=email.sent_at or email.created_at,
        )
        db.session.add(evidence)
    elif existing.application_id != record.id:
        raise ValueError("An email cannot be linked to more than one application.")

    if signal.get("deadline") and (record.deadline is None or signal["deadline"] < record.deadline):
        record.deadline = signal["deadline"]
    if signal.get("summary"):
        record.summary = str(signal["summary"]).strip()
    return record


def record_application_decision(
    record: ApplicationRecord,
    status: str,
    source: str,
    reason: str,
) -> ApplicationDecision:
    """Append a validated transition and update the current application state."""

    if status not in APPLICATION_STATUSES:
        raise ValueError("Unsupported application status.")
    reason = str(reason or "").strip()
    if source == "user" and not reason:
        raise ValueError("A user decision needs a reason.")

    record.status = status
    if status == "applied" and record.applied_at is None:
        record.applied_at = datetime.utcnow()
    decision = ApplicationDecision(
        application=record,
        status=status,
        source=source,
        reason=reason or "Inferred from linked evidence.",
    )
    db.session.add(decision)
    return decision


def _find_record(normalized_company, normalized_role, requisition_id, application_url):
    if requisition_id:
        match = ApplicationRecord.query.filter_by(requisition_id=requisition_id).one_or_none()
        if match:
            return match
    if application_url:
        match = ApplicationRecord.query.filter_by(application_url=application_url).one_or_none()
        if match:
            return match
    return ApplicationRecord.query.filter_by(
        normalized_company=normalized_company,
        normalized_role=normalized_role,
        requisition_id=None,
    ).one_or_none()


def _source_key(normalized_company, normalized_role, requisition_id, application_url):
    discriminator = requisition_id or application_url or normalized_role or "unknown-role"
    return f"application:{normalized_company}:{normalize_application_value(discriminator)}"[:240]
