from pathlib import Path

from flask import current_app

from automation_agent import AutomationEngine
from automation_agent.config import AutomationConfig
from runtime_paths import get_runtime_paths


_ENGINES = {}


def get_automation_engine():
    configured_data_dir = str(current_app.config.get("AIOS_DATA_DIR") or "").strip()
    base_data_dir = (
        Path(configured_data_dir).expanduser().resolve()
        if configured_data_dir
        else get_runtime_paths().data_dir
    )
    defaults = AutomationConfig.from_environment()
    key = str(base_data_dir)
    if key not in _ENGINES:
        _ENGINES[key] = AutomationEngine(
            AutomationConfig(
                data_dir=base_data_dir / "automation",
                allowed_roots=defaults.allowed_roots,
                max_batch_files=defaults.max_batch_files,
                max_extract_bytes=defaults.max_extract_bytes,
            )
        )
    return _ENGINES[key]


def automation_overview():
    engine = get_automation_engine()
    plans = engine.store.list_plans(limit=10)
    counts = {
        "plans": len(plans),
        "completed": sum(plan["status"] == "completed" for plan in plans),
        "failed": sum(plan["status"] in {"failed", "partial"} for plan in plans),
        "actions": sum(len(plan["actions"]) for plan in plans),
    }
    return {"plans": plans, "counts": counts, "capabilities": engine.capabilities()}
