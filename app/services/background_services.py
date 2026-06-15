import threading
from datetime import datetime, timezone


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
            "last_error": None,
        }


def record_service_run(service_id, error=None):
    with _lock:
        service = _services.get(service_id)
        if not service:
            return
        service["last_run_at"] = datetime.now(timezone.utc).isoformat()
        service["last_error"] = str(error) if error else None


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
