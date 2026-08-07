from datetime import datetime, timedelta, timezone

from app.services.time_utils import mail_time_details, normalize_gmail_datetime


def test_gmail_header_is_normalized_to_utc_without_losing_offset():
    parsed = normalize_gmail_datetime(
        "Fri, 07 Aug 2026 20:00:00 +0000",
        None,
    )

    assert parsed == datetime(2026, 8, 7, 20, 0)


def test_gmail_internal_date_is_normalized_to_utc():
    parsed = normalize_gmail_datetime(None, "1786132800000")

    assert parsed == datetime.fromtimestamp(1786132800000 / 1000, tz=timezone.utc).replace(tzinfo=None)


def test_mail_details_compares_provider_time_with_local_machine_clock():
    sent_at = datetime(2026, 8, 7, 20, 0)
    local_now = datetime(2026, 8, 8, 1, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    details = mail_time_details(sent_at, now=local_now)

    assert details["timestamp_utc"] == "2026-08-07T20:00:00Z"
    assert details["local_date"]
    assert details["age_seconds"] == 0
    assert details["age_label"] == "Just now"
    assert details["is_today"] is True
