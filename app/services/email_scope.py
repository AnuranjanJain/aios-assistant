from app.models import ConnectedAccount, EmailMessage, db


EMAIL_PORTFOLIO_LIMIT = 1000
EMAIL_BACKFILL_LIMIT_PER_ACCOUNT = 1000


def clamp_email_limit(limit=EMAIL_PORTFOLIO_LIMIT):
    return min(
        EMAIL_PORTFOLIO_LIMIT,
        max(1, int(limit or EMAIL_PORTFOLIO_LIMIT)),
    )


def latest_emails_combined(limit=EMAIL_PORTFOLIO_LIMIT):
    """Return the newest ``limit`` messages from each Google account.

    The account windows are deliberately selected before merging. A single
    busy inbox must never crowd another connected account out of analysis.
    The merged result is only a presentation/analysis view; stored messages
    remain durable and account-owned.
    """
    limit = clamp_email_limit(limit)
    occurred_at = db.func.coalesce(EmailMessage.sent_at, EmailMessage.created_at)
    messages = []
    accounts = ConnectedAccount.query.filter_by(provider="google").order_by(ConnectedAccount.id.asc()).all()
    for account in accounts:
        messages.extend(
            EmailMessage.query.filter_by(account_id=account.id)
            .order_by(occurred_at.desc(), EmailMessage.id.desc())
            .limit(limit)
            .all()
        )
    return sorted(
        messages,
        key=lambda email: (
            email.sent_at or email.created_at,
            email.id or 0,
        ),
        reverse=True,
    )


def latest_email_ids_combined(limit=EMAIL_PORTFOLIO_LIMIT):
    return [
        email.id
        for email in latest_emails_combined(limit)
        if email.id is not None
    ]
