import hashlib
import hmac
import ipaddress
from urllib.parse import urlsplit


READ_ONLY_OPERATIONS = {
    "open",
    "navigate",
    "extract_jobs",
    "extract_page",
    "manage_tabs",
}
EXTERNAL_SIDE_EFFECTS = {
    "click_submit",
    "send_message",
    "upload_file",
    "accept_permission",
    "save_password",
}
SENSITIVE_FIELDS = {
    "address",
    "date_of_birth",
    "email",
    "phone",
    "password",
    "salary",
    "social_security",
}


class BrowserSafetyError(ValueError):
    pass


class BrowserSafety:
    def __init__(self, config):
        self.config = config

    def validate_url(self, url):
        parsed = urlsplit(str(url).strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise BrowserSafetyError("Only explicit HTTP or HTTPS URLs are supported.")
        hostname = parsed.hostname.lower().rstrip(".")
        try:
            address = ipaddress.ip_address(hostname)
            if address.is_private or address.is_loopback or address.is_link_local:
                raise BrowserSafetyError("Private and loopback browser targets are blocked.")
        except ValueError:
            pass
        if not any(hostname == domain or hostname.endswith(f".{domain}") for domain in self.config.allowed_domains):
            raise BrowserSafetyError(f"Domain is not approved for browser automation: {hostname}")
        if parsed.username or parsed.password:
            raise BrowserSafetyError("Credentials must not be embedded in URLs.")
        return parsed.geturl()

    @staticmethod
    def action_risk(operation, arguments):
        if operation in EXTERNAL_SIDE_EFFECTS:
            return "critical"
        if operation == "fill_form":
            fields = {str(key).lower() for key in arguments.get("fields", {})}
            return "high" if fields & SENSITIVE_FIELDS else "medium"
        if operation == "download":
            return "medium"
        if operation == "click":
            return "medium"
        return "low"

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def token_matches(cls, token, expected_hash):
        return bool(token and expected_hash) and hmac.compare_digest(
            cls.token_hash(token), expected_hash
        )
