from automation_agent.config import AutomationConfig
from automation_agent.planner import TaskPlanner
from automation_agent.safety import SafetyValidator
from automation_agent.store import AutomationStore, generate_approval_token
from automation_agent.tools import DesktopTools, FileTools, OfficeTools, ScreenshotTools


class AutomationEngine:
    def __init__(self, config=None):
        self.config = (config or AutomationConfig.from_environment()).ensure()
        self.safety = SafetyValidator(self.config)
        self.store = AutomationStore(self.config.data_dir / "automation.db")
        self.planner = TaskPlanner(self.config, self.safety)
        self.tools = {
            "files": FileTools(self.config, self.safety),
            "office": OfficeTools(self.safety),
            "screenshot": ScreenshotTools(self.safety),
            "desktop": DesktopTools(),
        }

    def create_plan(self, request_text, parameters=None):
        plan = self.planner.create(request_text, parameters)
        token = generate_approval_token()
        self.store.create_plan(plan, self.safety.token_hash(token))
        saved = self.store.get_plan(plan["id"])
        saved["approval_token"] = token
        saved["preview"] = self._preview(saved)
        return saved

    def execute_plan(self, plan_id, approval_token):
        plan = self.store.get_plan(plan_id)
        if plan is None:
            raise KeyError("Automation plan was not found.")
        if plan["status"] != "planned":
            raise ValueError(f"Plan is already {plan['status']}.")
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT approval_hash FROM automation_plan WHERE id = ?", (plan_id,)
            ).fetchone()
        if not self.safety.token_matches(approval_token, row["approval_hash"]):
            raise PermissionError("The plan approval token is missing or invalid.")

        self.store.set_plan_status(plan_id, "running")
        failures = 0
        for action in plan["actions"]:
            self.store.start_action(action["id"])
            try:
                tool = self.tools[action["tool"]]
                if action["tool"] == "screenshot":
                    result = tool.analyze(**action["arguments"])
                else:
                    result = tool.execute(action["operation"], action["arguments"])
                self._verify(action, result)
                self.store.finish_action(action["id"], "completed", result.as_dict())
            except Exception as exc:
                failures += 1
                self.store.finish_action(action["id"], "failed", error=str(exc))
        status = "completed" if not failures else ("failed" if failures == len(plan["actions"]) else "partial")
        self.store.set_plan_status(plan_id, status)
        return self.store.get_plan(plan_id)

    def restore_action(self, action_id):
        with self.store.connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM automation_action WHERE id = ? AND operation = 'quarantine'",
                (action_id,),
            ).fetchone()
        if row is None:
            raise KeyError("A reversible quarantine action was not found.")
        import json

        result = json.loads(row["result_json"] or "{}")
        data = result.get("data", {})
        restored = self.tools["files"].restore(data["quarantined"], data["original"])
        return restored.as_dict()

    @staticmethod
    def _verify(action, result):
        if not result.ok:
            raise RuntimeError(result.summary)
        if action["operation"] in {"create_folders", "move", "rename", "compress", "extract", "create_docx", "create_pptx", "create_spreadsheet", "weekly_excel_report", "convert_to_pdf"}:
            from pathlib import Path

            missing = [path for path in result.changed_paths if not Path(path).exists()]
            if missing:
                raise RuntimeError(f"Verification failed for: {', '.join(missing)}")

    @staticmethod
    def _preview(plan):
        return [
            f"{action['operation'].replace('_', ' ').title()}: "
            + ", ".join(f"{key}={value}" for key, value in action["arguments"].items())
            for action in plan["actions"]
        ]

    def capabilities(self):
        import shutil

        return {
            "local_only": True,
            "audit_database": str(self.store.database_path),
            "allowed_roots": [str(path) for path in self.config.allowed_roots],
            "file_tools": ["organize", "move", "rename", "quarantine", "restore", "duplicates", "compress", "extract"],
            "office_tools": ["DOCX", "PPTX", "XLSX", "PDF via LibreOffice"],
            "screenshot_ocr": bool(shutil.which("tesseract")),
            "libreoffice": bool(shutil.which("soffice") or shutil.which("libreoffice")),
            "desktop_control_enabled": self.tools["desktop"].enabled,
        }
