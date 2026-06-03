from app.models import Setting, db


SETTING_KEYS = {
    "AI_PROVIDER": "AI provider",
    "OLLAMA_URL": "Ollama URL",
    "OLLAMA_MODEL": "Ollama model",
    "GMAIL_MBOX_PATH": "Gmail Takeout mbox path",
    "GMAIL_CREDENTIALS_PATH": "Gmail credentials path",
    "GMAIL_TOKEN_PATH": "Gmail token path",
    "JOB_PORTAL_IMPORT_DIR": "Job portal import folder",
    "WATCH_IMPORT_DIR": "Watch import folder",
}


def get_setting(key, default=""):
    row = db.session.get(Setting, key)
    if row and row.value is not None:
        return row.value
    return default


def set_setting(key, value):
    row = db.session.get(Setting, key)
    if row is None:
        row = Setting(key=key)
        db.session.add(row)
    row.value = value
    return row


def get_effective_config(app_config):
    values = {}
    for key in SETTING_KEYS:
        values[key] = get_setting(key, app_config.get(key, ""))
    return values


def apply_settings(form):
    for key in SETTING_KEYS:
        if key in form:
            set_setting(key, form.get(key, "").strip())
