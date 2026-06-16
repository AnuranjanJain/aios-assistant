import os
from dataclasses import dataclass
from pathlib import Path

from runtime_paths import get_runtime_paths


DEFAULT_PROJECT_NAMES = (
    "AiOS",
    "What Do You Do",
    "Healthcare App",
    "Video Enhancer",
    "Hackathon Projects",
)


@dataclass(frozen=True)
class CareerConfig:
    data_dir: Path
    github_token: str = ""
    max_files_per_repo: int = 1600
    max_file_bytes: int = 350_000
    project_names: tuple[str, ...] = DEFAULT_PROJECT_NAMES

    @classmethod
    def from_environment(cls):
        projects = tuple(
            item.strip()
            for item in os.getenv("AIOS_CAREER_PROJECTS", "").split(",")
            if item.strip()
        ) or DEFAULT_PROJECT_NAMES
        return cls(
            data_dir=get_runtime_paths().data_dir / "career-copilot",
            github_token=os.getenv("GITHUB_TOKEN", "").strip(),
            project_names=projects,
        )

    def ensure(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "reports").mkdir(exist_ok=True)
        return self
