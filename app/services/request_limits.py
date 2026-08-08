"""Small request guards shared by the standalone local agent APIs."""

from fastapi import Request
from fastapi.responses import JSONResponse


def install_request_size_limit(app, max_bytes=256 * 1024):
    @app.middleware("http")
    async def reject_oversized_requests(request: Request, call_next):
        raw_length = request.headers.get("content-length", "")
        try:
            content_length = int(raw_length) if raw_length else 0
        except ValueError:
            content_length = 0
        if content_length > max_bytes:
            return JSONResponse(
                {"ok": False, "error": "request_too_large", "message": "Request exceeds the local agent limit."},
                status_code=413,
            )
        return await call_next(request)

