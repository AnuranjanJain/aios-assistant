from app.models import Setting, db


SETTING_KEYS = {
    "AI_PROVIDER": "AI provider",
    "OLLAMA_URL": "Ollama URL",
    "OLLAMA_MODEL": "Ollama model",
    "OLLAMA_EMBED_MODEL": "Ollama embedding model",
    "MEMORY_VECTOR_BACKEND": "Memory vector backend (auto, chroma, faiss, sqlite)",
    "MEMORY_VECTOR_PATH": "Memory vector storage path",
    "GMAIL_MBOX_PATH": "Gmail Takeout mbox path",
    "GMAIL_OPPORTUNITY_QUERY": "Gmail opportunity search query",
    "GMAIL_HACKATHON_QUERY": "Legacy Gmail hackathon search query",
    "EMAIL_SYNC_INTERVAL_MINUTES": "Email intelligence sync interval (minutes)",
    "JOB_PORTAL_IMPORT_DIR": "Job portal import folder",
    "HACKATHON_IMPORT_DIR": "Hackathon platform import folder",
    "HACKATHON_SCAN_INTERVAL_MINUTES": "Opportunity scan interval (minutes)",
    "WATCH_IMPORT_DIR": "Watch import folder",
    "GITHUB_TOKEN": "GitHub token for private repo activity",
    "LOCAL_API_TOKEN": "Local API token",
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
