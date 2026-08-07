"""Local-machine clock helpers and provider timestamp normalization."""

from __future__ import annotations

from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime


UTC = timezone.utc


def local_now() -> datetime:
    """Return the machine's current local wall clock as a naive datetime."""
    return datetime.now().astimezone().replace(tzinfo=None)


def local_today() -> date:
    return local_now().date()


def utc_now_naive() -> datetime:
    """Return UTC without tzinfo for compatibility with SQLite naive columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_gmail_datetime(header_date, internal_date) -> datetime:
    """Store Gmail instants as UTC-naive values regardless of provider format."""
    parsed = None
    if header_date:
        try:
            parsed = parsedate_to_datetime(str(header_date))
        except (TypeError, ValueError, OverflowError):
            parsed = None
    if parsed is None and internal_date:
        try:
            parsed = datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
        except (TypeError, ValueError, OverflowError, OSError):
            parsed = None
    if parsed is None:
        return utc_now_naive()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def as_local(value: datetime, zone=None) -> datetime:
    zone = zone or datetime.now().astimezone().tzinfo
    return _as_utc(value).astimezone(zone)


def utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_local(value).isoformat(timespec="seconds")


def local_timezone_label() -> str:
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    formatted_offset = f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else offset
    return f"{now.tzname() or 'local'} (UTC{formatted_offset})"


def machine_clock() -> dict:
    now = datetime.now().astimezone()
    return {
        "local_now": now.isoformat(timespec="seconds"),
        "utc_now": now.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "local_date": now.date().isoformat(),
        "timezone": local_timezone_label(),
    }


def mail_time_details(value: datetime | None, now: datetime | None = None) -> dict:
    """Describe a stored mail instant relative to the local machine clock."""
    if value is None:
        return {
            "timestamp_utc": None,
            "timestamp_local": None,
            "local_date": None,
            "is_today": False,
            "age_seconds": None,
            "age_label": "Date unknown",
            "timezone": local_timezone_label(),
        }
    reference = now or datetime.now().astimezone()
    if reference.tzinfo is None:
        reference = reference.astimezone()
    local_value = as_local(value, reference.tzinfo)
    delta_seconds = int((reference - local_value).total_seconds())
    absolute_seconds = abs(delta_seconds)
    if delta_seconds < -60:
        minutes = max(1, absolute_seconds // 60)
        age_label = f"in {minutes}m" if minutes < 60 else f"in {max(1, minutes // 60)}h"
    elif absolute_seconds < 60:
        age_label = "Just now"
    elif absolute_seconds < 3600:
        age_label = f"{absolute_seconds // 60}m ago"
    elif absolute_seconds < 86400:
        age_label = f"{absolute_seconds // 3600}h ago"
    elif absolute_seconds < 172800:
        age_label = "Yesterday"
    else:
        age_label = f"{absolute_seconds // 86400}d ago"
    return {
        "timestamp_utc": utc_iso(value),
        "timestamp_local": local_value.isoformat(timespec="seconds"),
        "local_date": local_value.date().isoformat(),
        "is_today": local_value.date() == reference.date(),
        "age_seconds": delta_seconds,
        "age_label": age_label,
        "timezone": local_timezone_label(),
    }
