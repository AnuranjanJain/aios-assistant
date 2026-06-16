from pathlib import Path

from flask import current_app

from career_agent import CareerCopilotEngine
from career_agent.config import CareerConfig
from runtime_paths import get_runtime_paths


_ENGINES = {}


def get_career_engine():
    configured_data_dir = str(current_app.config.get("AIOS_DATA_DIR") or "").strip()
    base_data_dir = (
        Path(configured_data_dir).expanduser().resolve()
        if configured_data_dir
        else get_runtime_paths().data_dir
    )
    defaults = CareerConfig.from_environment()
    key = str(base_data_dir)
    if key not in _ENGINES:
        _ENGINES[key] = CareerCopilotEngine(
            CareerConfig(
                data_dir=base_data_dir / "career-copilot",
                github_token=defaults.github_token,
                max_files_per_repo=defaults.max_files_per_repo,
                max_file_bytes=defaults.max_file_bytes,
                project_names=defaults.project_names,
            )
        )
    return _ENGINES[key]


def career_overview():
    return get_career_engine().dashboard()
