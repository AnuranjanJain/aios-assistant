import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path


STATE_PATH = Path(os.getenv("AIOS_WORKERS_STATE_PATH", ".aios_workers.json"))


@dataclass
class WorkerDefinition:
    worker_id: str
    name: str
    script: str
    description: str


WORKERS = {
    "reminders": WorkerDefinition(
        worker_id="reminders",
        name="Reminder Worker",
        script="local_worker.py",
        description="Checks due reminders and sends local desktop notifications.",
    ),
    "activity": WorkerDefinition(
        worker_id="activity",
        name="Desktop Activity Worker",
        script="desktop_activity_worker.py",
        description="Tracks active desktop windows and logs wellbeing activity.",
    ),
    "watch_imports": WorkerDefinition(
        worker_id="watch_imports",
        name="Watch Import Worker",
        script="watch_import_worker.py",
        description="Imports real files dropped into the configured watch folder.",
    ),
    "hackathons": WorkerDefinition(
        worker_id="hackathons",
        name="Opportunity Monitor",
        script="hackathon_monitor_worker.py",
        description="Scans Gmail, hackathon exports, and job portal exports for live opportunity updates.",
    ),
    "email_intelligence": WorkerDefinition(
        worker_id="email_intelligence",
        name="Email Intelligence Planner",
        script="email_intelligence_worker.py",
        description="Syncs connected Gmail accounts, analyzes email locally, and refreshes daily/weekly plans.",
    ),
}


def load_state():
    if not STATE_PATH.exists():
        return {}

    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def list_worker_status():
    state = load_state()
    statuses = [worker_status(worker, state) for worker in WORKERS.values()]
    try:
        from app.services.background_services import list_background_services

        managed = {item["id"]: item for item in list_background_services()}
        aliases = {"opportunities": "hackathons"}
        for service_id, service in managed.items():
            worker_id = aliases.get(service_id, service_id)
            existing = next((item for item in statuses if item["id"] == worker_id), None)
            if existing:
                existing.update(
                    {
                        "running": service["running"],
                        "managed": True,
                        "last_run_at": service["last_run_at"],
                        "last_error": service["last_error"],
                    }
                )
    except ImportError:
        pass
    activity = next((item for item in statuses if item["id"] == "activity"), None)
    if activity:
        try:
            with urllib.request.urlopen("http://127.0.0.1:17321/health", timeout=0.4) as response:
                health = json.loads(response.read().decode("utf-8"))
            if health.get("ok"):
                activity.update(
                    {
                        "running": True,
                        "managed": True,
                        "description": "Tracks privacy-filtered desktop activity through What Do You Do.",
                        "last_run_at": health.get("latestCapturedAt"),
                        "last_error": health.get("lastError"),
                    }
                )
        except (OSError, ValueError):
            pass
    return statuses


def worker_status(worker, state=None):
    state = state if state is not None else load_state()
    pid = state.get(worker.worker_id, {}).get("pid")
    running = bool(pid and is_pid_running(pid))

    return {
        "id": worker.worker_id,
        "name": worker.name,
        "script": worker.script,
        "description": worker.description,
        "pid": pid if running else None,
        "running": running,
    }


def start_worker(worker_id):
    worker = WORKERS.get(worker_id)
    if not worker:
        return {"status": "not_found", "message": f"Unknown worker: {worker_id}"}

    state = load_state()
    current = worker_status(worker, state)
    try:
        from app.services.background_services import list_background_services

        aliases = {"hackathons": "opportunities"}
        managed_id = aliases.get(worker_id, worker_id)
        managed = next((item for item in list_background_services() if item["id"] == managed_id), None)
        if managed and managed["running"]:
            return {
                "status": "already_running",
                "message": f"{worker.name} is managed by the desktop app.",
                "worker": current | {"running": True, "managed": True},
            }
    except ImportError:
        pass
    if current["running"]:
        return {"status": "already_running", "message": f"{worker.name} is already running.", "worker": current}

    if getattr(sys, "frozen", False):
        command = [sys.executable, "--worker", worker.worker_id]
    else:
        command = [sys.executable, worker.script]
    kwargs = {
        "cwd": Path.cwd(),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }

    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    process = subprocess.Popen(command, **kwargs)
    state[worker.worker_id] = {"pid": process.pid}
    save_state(state)

    return {
        "status": "started",
        "message": f"{worker.name} started.",
        "worker": worker_status(worker, state),
    }


def stop_worker(worker_id):
    worker = WORKERS.get(worker_id)
    if not worker:
        return {"status": "not_found", "message": f"Unknown worker: {worker_id}"}

    state = load_state()
    pid = state.get(worker.worker_id, {}).get("pid")
    if not pid or not is_pid_running(pid):
        state.pop(worker.worker_id, None)
        save_state(state)
        return {"status": "not_running", "message": f"{worker.name} is not running."}

    stop_pid(pid)
    state.pop(worker.worker_id, None)
    save_state(state)

    return {"status": "stopped", "message": f"{worker.name} stopped."}


def is_pid_running(pid):
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout

    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def stop_pid(pid):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        return

    os.kill(int(pid), 15)
