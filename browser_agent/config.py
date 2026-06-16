import os
from dataclasses import dataclass
from pathlib import Path

from runtime_paths import get_runtime_paths


DEFAULT_ALLOWED_DOMAINS = (
    "linkedin.com",
    "internshala.com",
    "wellfound.com",
    "naukri.com",
    "indeed.com",
    "google.com",
    "bing.com",
)


@dataclass(frozen=True)
class BrowserAgentConfig:
    data_dir: Path
    allowed_domains: tuple[str, ...] = DEFAULT_ALLOWED_DOMAINS
    headless: bool = False
    max_pages_per_run: int = 20
    max_results_per_run: int = 100

    @classmethod
    def from_environment(cls):
        data_dir = get_runtime_paths().data_dir / "browser-agent"
        domains = tuple(
            item.strip().lower()
            for item in os.getenv("AIOS_BROWSER_ALLOWED_DOMAINS", "").split(",")
            if item.strip()
        ) or DEFAULT_ALLOWED_DOMAINS
        return cls(
            data_dir=data_dir,
            allowed_domains=domains,
            headless=os.getenv("AIOS_BROWSER_HEADLESS", "") == "1",
        )

    def ensure(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "downloads").mkdir(exist_ok=True)
        (self.data_dir / "reports").mkdir(exist_ok=True)
        return self
