"""Local-only network policy shared by AI and companion integrations."""

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LocalSecurityError(ValueError):
    """Raised when a local-only service is configured outside the device."""


def is_loopback_hostname(hostname):
    hostname = str(hostname or "").lower().rstrip(".")
    if hostname in LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        pass

    # Resolve named hosts before allowing a request. This prevents a friendly
    # hostname from silently pointing at a private or public interface.
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        }
    except OSError:
        return False
    return bool(addresses) and all(ipaddress.ip_address(address).is_loopback for address in addresses)


def is_loopback_url(value):
    parsed = urlsplit(str(value or "").strip())
    return (
        parsed.scheme in {"http", "https"}
        and bool(parsed.hostname)
        and not parsed.username
        and not parsed.password
        and is_loopback_hostname(parsed.hostname)
    )


def validate_local_url(value, default="http://127.0.0.1:11434"):
    candidate = str(value or default).strip()
    parsed = urlsplit(candidate)
    if not is_loopback_url(candidate):
        raise LocalSecurityError("Local service URLs must use HTTP(S) on a loopback address.")
    if parsed.query or parsed.fragment:
        raise LocalSecurityError("Local service URLs must not contain a query or fragment.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise LocalSecurityError("Local service URL has an invalid port.") from exc
    if port is not None and not 1 <= port <= 65535:
        raise LocalSecurityError("Local service URL has an invalid port.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def safe_ollama_url(config):
    try:
        return validate_local_url(config.get("OLLAMA_URL") or "http://localhost:11434")
    except LocalSecurityError as exc:
        raise LocalSecurityError(f"Ollama URL must stay on loopback. {exc}") from exc
