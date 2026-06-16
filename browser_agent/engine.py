import secrets

from browser_agent.config import BrowserAgentConfig
from browser_agent.planner import BrowserTaskPlanner
from browser_agent.safety import BrowserSafety, EXTERNAL_SIDE_EFFECTS
from browser_agent.scoring import score_opportunity
from browser_agent.store import BrowserAgentStore
from browser_agent.tools import PlaywrightBrowserBackend


class BrowserAgentEngine:
    def __init__(self, config=None, backend=None):
        self.config = (config or BrowserAgentConfig.from_environment()).ensure()
        self.safety = BrowserSafety(self.config)
        self.store = BrowserAgentStore(self.config.data_dir / "browser_agent.db")
        self.planner = BrowserTaskPlanner(self.safety)
        self.backend = backend or PlaywrightBrowserBackend(self.config)

    def create_plan(self, request_text, parameters=None):
        plan = self.planner.create(request_text, parameters)
        token = secrets.token_urlsafe(18)
        self.store.create_plan(plan, self.safety.token_hash(token))
        saved = self.store.get_plan(plan["id"])
        saved["approval_token"] = token
        saved["preview"] = [
            f"{action['operation'].replace('_', ' ').title()} [{action['risk_level']}]: "
            + ", ".join(f"{key}={value}" for key, value in action["arguments"].items())
            for action in saved["actions"]
        ]
        return saved

    def execute_plan(self, plan_id, approval_token="", profile=None):
        plan = self.store.get_plan(plan_id)
        if plan is None:
            raise KeyError("Browser plan was not found.")
        if plan["status"] != "planned":
            raise ValueError(f"Plan is already {plan['status']}.")
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT approval_hash FROM browser_plan WHERE id=?", (plan_id,)
            ).fetchone()
        if plan["risk_level"] in {"high", "critical"} and not self.safety.token_matches(
            approval_token, row["approval_hash"]
        ):
            raise PermissionError("Approval token is required for form preparation.")

        self.store.set_plan_status(plan_id, "running")
        failed = 0
        awaiting = False
        try:
            for action in plan["actions"]:
                if action["operation"] in EXTERNAL_SIDE_EFFECTS:
                    awaiting = True
                    self.store.finish_action(
                        action["id"],
                        "awaiting_approval",
                        {"summary": "External submission stopped for action-time human approval."},
                    )
                    continue
                self.store.start_action(action["id"])
                try:
                    result = getattr(self.backend, action["operation"])(**action["arguments"])
                    data = result.as_dict()
                    if action["operation"] == "extract_jobs":
                        saved = self._score_and_save(data.get("data", {}).get("jobs", []), profile or {})
                        data["data"]["saved_opportunities"] = saved
                    self.store.finish_action(action["id"], "completed", data)
                except Exception as exc:
                    failed += 1
                    self.store.finish_action(action["id"], "failed", error=str(exc))
        finally:
            self.backend.close()

        status = "awaiting_approval" if awaiting and not failed else "failed" if failed == len(plan["actions"]) else "partial" if failed else "completed"
        self.store.set_plan_status(plan_id, status)
        return self.store.get_plan(plan_id)

    def _score_and_save(self, jobs, profile):
        saved = []
        for job in jobs[: self.config.max_results_per_run]:
            job["source_url"] = self.safety.validate_url(job["source_url"])
            score, reason = score_opportunity(job, profile)
            job["match_score"] = score
            job["score_reason"] = reason
            saved.append(self.store.save_opportunity(job))
        return saved

    def capabilities(self):
        try:
            import playwright  # noqa: F401
            playwright_installed = True
        except ImportError:
            playwright_installed = False
        return {
            "local_first": True,
            "database": str(self.store.database_path),
            "allowed_domains": list(self.config.allowed_domains),
            "playwright_installed": playwright_installed,
            "submission_enabled": False,
            "browser_mcp_bridge": True,
        }
