import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


STATE_PATH = Path(".aios_workers.json")


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
    return [worker_status(worker, state) for worker in WORKERS.values()]


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
    if current["running"]:
        return {"status": "already_running", "message": f"{worker.name} is already running.", "worker": current}

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
