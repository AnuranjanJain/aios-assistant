from werkzeug.security import check_password_hash, generate_password_hash

from app.models import Setting
from app.services.settings import get_setting, set_setting


PIN_HASH_KEY = "AUTH_PIN_HASH"


def has_pin():
    return bool(get_setting(PIN_HASH_KEY, ""))


def set_pin(pin):
    set_setting(PIN_HASH_KEY, generate_password_hash(pin))


def verify_pin(pin):
    stored = get_setting(PIN_HASH_KEY, "")
    return bool(stored and check_password_hash(stored, pin))


def clear_pin():
    row = Setting.query.get(PIN_HASH_KEY)
    if row:
        row.value = ""
