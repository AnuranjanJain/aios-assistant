from hmac import compare_digest

from app.services.settings import get_setting


TOKEN_HEADER = "X-AiOS-Token"


def has_valid_api_token(request, app_config):
    expected = get_setting("LOCAL_API_TOKEN", app_config.get("LOCAL_API_TOKEN", "")).strip()
    supplied = request.headers.get(TOKEN_HEADER, "").strip()

    return bool(expected and supplied and compare_digest(supplied, expected))
