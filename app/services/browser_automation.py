from pathlib import Path

from flask import current_app

from browser_agent import BrowserAgentEngine
from browser_agent.config import BrowserAgentConfig
from runtime_paths import get_runtime_paths


_ENGINES = {}


def get_browser_agent():
    configured_data_dir = str(current_app.config.get("AIOS_DATA_DIR") or "").strip()
    base_data_dir = (
        Path(configured_data_dir).expanduser().resolve()
        if configured_data_dir
        else get_runtime_paths().data_dir
    )
    defaults = BrowserAgentConfig.from_environment()
    key = str(base_data_dir)
    if key not in _ENGINES:
        _ENGINES[key] = BrowserAgentEngine(
            BrowserAgentConfig(
                data_dir=base_data_dir / "browser-agent",
                allowed_domains=defaults.allowed_domains,
                headless=defaults.headless,
                max_pages_per_run=defaults.max_pages_per_run,
                max_results_per_run=defaults.max_results_per_run,
            )
        )
    return _ENGINES[key]


def browser_agent_overview():
    engine = get_browser_agent()
    plans = engine.store.list_plans(limit=10)
    opportunities = engine.store.list_opportunities(limit=50)
    counts = {
        "plans": len(plans),
        "opportunities": len(opportunities),
        "high_match": sum(item["match_score"] >= 70 for item in opportunities),
        "awaiting": sum(plan["status"] == "awaiting_approval" for plan in plans),
    }
    return {
        "plans": plans,
        "opportunities": opportunities,
        "counts": counts,
        "capabilities": engine.capabilities(),
    }
