"""One-time approval handshake for the native companion client."""

import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


PAIRING_TTL_SECONDS = 120


@dataclass
class PendingPairing:
    expires_at: datetime
    approved_token: str = ""


_LOCK = threading.Lock()
_PENDING = {}
_NATIVE_SECRET_LOCK = threading.Lock()
_CONSUMED_NATIVE_SECRETS = set()


def _now():
    return datetime.now(timezone.utc)


def _purge(now=None):
    now = now or _now()
    for challenge, item in list(_PENDING.items()):
        if item.expires_at <= now:
            _PENDING.pop(challenge, None)


def issue_challenge():
    challenge = secrets.token_urlsafe(24)
    with _LOCK:
        _purge()
        _PENDING[challenge] = PendingPairing(
            expires_at=_now() + timedelta(seconds=PAIRING_TTL_SECONDS)
        )
    return challenge


def approve_challenge(challenge, token):
    with _LOCK:
        _purge()
        item = _PENDING.get(str(challenge or ""))
        if item is None:
            return False
        item.approved_token = str(token or "")
        return True


def consume_approved_token(challenge):
    with _LOCK:
        _purge()
        item = _PENDING.pop(str(challenge or ""), None)
        if item is None or not item.approved_token:
            return ""
        return item.approved_token


def challenge_status(challenge):
    with _LOCK:
        _purge()
        item = _PENDING.get(str(challenge or ""))
        if item is None:
            return None
        return {
            "approved": bool(item.approved_token),
            "expires_at": item.expires_at.isoformat(),
        }


def consume_native_secret(expected, supplied):
    """Allow a core process launched by the native shell to pair once."""
    if not expected or not supplied:
        return False
    with _NATIVE_SECRET_LOCK:
        expected = str(expected)
        if expected in _CONSUMED_NATIVE_SECRETS:
            return False
        if secrets.compare_digest(expected, str(supplied)):
            _CONSUMED_NATIVE_SECRETS.add(expected)
            return True
    return False
