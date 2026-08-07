"""Authentication dependency for the standalone local agent APIs."""

import hmac
import os

from fastapi import Header, HTTPException


def _configured_token():
    return (
        os.getenv("AIOS_AGENT_API_TOKEN", "").strip()
        or os.getenv("LOCAL_API_TOKEN", "").strip()
    )


def require_agent_token(
    x_aios_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    expected = _configured_token()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Local agent API authentication is not configured.",
        )
    supplied = (x_aios_token or "").strip()
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="A valid AiOS local API token is required.")
    return True
