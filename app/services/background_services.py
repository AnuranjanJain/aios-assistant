import threading
from datetime import datetime, timedelta, timezone


_lock = threading.Lock()
_services = {}


def register_service(service_id, name, description, thread=None):
    with _lock:
        _services[service_id] = {
            "id": service_id,
            "name": name,
            "description": description,
            "thread": thread,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_run_at": None,
            "last_success_at": None,
            "last_error": None,
            "failure_count": 0,
            "last_duration_ms": None,
            "next_run_at": None,
        }


def record_service_run(service_id, error=None, duration_ms=None, retry_after=None):
    with _lock:
        service = _services.get(service_id)
        if not service:
            return
        now = datetime.now(timezone.utc)
        service["last_run_at"] = now.isoformat()
        service["last_error"] = str(error) if error else None
        service["last_duration_ms"] = round(float(duration_ms), 2) if duration_ms is not None else None
        if error:
            service["failure_count"] = int(service.get("failure_count") or 0) + 1
            service["next_run_at"] = (
                now + timedelta(seconds=max(1, int(retry_after or 0)))
            ).isoformat()
        else:
            service["failure_count"] = 0
            service["last_success_at"] = now.isoformat()
            service["next_run_at"] = None


def unregister_service(service_id):
    with _lock:
        _services.pop(service_id, None)


def list_background_services():
    with _lock:
        return [
            {
                key: value
                for key, value in service.items()
                if key != "thread"
            }
            | {"running": bool(service.get("thread") and service["thread"].is_alive())}
            for service in _services.values()
        ]
