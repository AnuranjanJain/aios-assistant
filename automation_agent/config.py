import os
from dataclasses import dataclass
from pathlib import Path

from runtime_paths import get_runtime_paths


def _default_roots():
    home = Path.home()
    candidates = (home / "Desktop", home / "Documents", home / "Downloads")
    return tuple(path.resolve() for path in candidates if path.exists())


@dataclass(frozen=True)
class AutomationConfig:
    data_dir: Path
    allowed_roots: tuple[Path, ...]
    max_batch_files: int = 500
    max_extract_bytes: int = 2 * 1024 * 1024 * 1024

    @classmethod
    def from_environment(cls):
        data_dir = get_runtime_paths().data_dir / "automation"
        raw_roots = os.getenv("AIOS_AUTOMATION_ALLOWED_ROOTS", "").strip()
        roots = tuple(
            Path(value).expanduser().resolve()
            for value in raw_roots.split(os.pathsep)
            if value.strip()
        ) or _default_roots()
        return cls(data_dir=data_dir, allowed_roots=roots)

    def ensure(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "quarantine").mkdir(parents=True, exist_ok=True)
        return self
