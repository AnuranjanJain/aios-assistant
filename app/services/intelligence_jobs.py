"""Single-flight background execution for local intelligence refreshes."""

from __future__ import annotations

from datetime import datetime
from threading import Lock, Thread
from uuid import uuid4


class IntelligenceJobRegistry:
    def __init__(self):
        self._lock = Lock()
        self._jobs: dict[str, dict[str, object]] = {}
        self._active_job_id: str | None = None

    def start(self, operation):
        with self._lock:
            if self._active_job_id:
                job = self._jobs[self._active_job_id]
                return {"job_id": self._active_job_id, "status": job["status"], "reused": True}
            job_id = uuid4().hex
            self._jobs[job_id] = {
                "id": job_id,
                "status": "running",
                "phase": "starting",
                "created_at": datetime.utcnow().isoformat(),
                "result": None,
                "error": None,
            }
            self._active_job_id = job_id
        Thread(target=self._run, args=(job_id, operation), daemon=True).start()
        return {"job_id": job_id, "status": "running", "reused": False}

    def status(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return dict(job)

    def _run(self, job_id, operation):
        try:
            with self._lock:
                self._jobs[job_id]["phase"] = "syncing"
            result = operation()
            with self._lock:
                self._jobs[job_id].update({"status": "completed", "phase": "completed", "result": result})
        except Exception as error:
            with self._lock:
                self._jobs[job_id].update(
                    {
                        "status": "failed",
                        "phase": "failed",
                        "error": "Local intelligence sync failed. Check account status and retry once.",
                    }
                )
        finally:
            with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None


intelligence_jobs = IntelligenceJobRegistry()
