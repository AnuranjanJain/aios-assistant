from app.models import ConnectedAccount, EmailMessage, db


EMAIL_PORTFOLIO_LIMIT = 500
EMAIL_BACKFILL_LIMIT_PER_ACCOUNT = 500


def clamp_email_limit(limit=EMAIL_PORTFOLIO_LIMIT):
    return min(
        EMAIL_PORTFOLIO_LIMIT,
        max(1, int(limit or EMAIL_PORTFOLIO_LIMIT)),
    )


def latest_emails_combined(limit=EMAIL_PORTFOLIO_LIMIT):
    """Return one globally ordered mail window across every Google account."""
    limit = clamp_email_limit(limit)
    occurred_at = db.func.coalesce(EmailMessage.sent_at, EmailMessage.created_at)
    return (
        EmailMessage.query.join(
            ConnectedAccount,
            EmailMessage.account_id == ConnectedAccount.id,
        )
        .filter(ConnectedAccount.provider == "google")
        .order_by(occurred_at.desc(), EmailMessage.id.desc())
        .limit(limit)
        .all()
    )


def latest_email_ids_combined(limit=EMAIL_PORTFOLIO_LIMIT):
    return [
        email.id
        for email in latest_emails_combined(limit)
        if email.id is not None
    ]
