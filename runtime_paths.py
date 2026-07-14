import os
import sys
from dataclasses import dataclass
from pathlib import Path


APP_DIR_NAME = "AiOS Assistant"
LINUX_DIR_NAME = "aios-assistant"


@dataclass(frozen=True)
class RuntimePaths:
    data_dir: Path
    config_dir: Path
    cache_dir: Path
    logs_dir: Path
    imports_dir: Path
    credentials_dir: Path
    instance_dir: Path

    def ensure(self):
        for path in (
            self.data_dir,
            self.config_dir,
            self.cache_dir,
            self.logs_dir,
            self.imports_dir,
            self.credentials_dir,
            self.instance_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        return self


def get_runtime_paths():
    override = os.getenv("AIOS_DATA_DIR", "").strip()
    if override:
        data_dir = Path(override).expanduser().resolve()
        config_dir = data_dir / "config"
        cache_dir = data_dir / "cache"
    elif sys.platform == "win32":
        data_dir = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData/Local") / APP_DIR_NAME
        config_dir = Path(os.getenv("APPDATA") or Path.home() / "AppData/Roaming") / APP_DIR_NAME
        cache_dir = data_dir / "cache"
    else:
        data_dir = Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local/share") / LINUX_DIR_NAME
        config_dir = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config") / LINUX_DIR_NAME
        cache_dir = Path(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache") / LINUX_DIR_NAME

    return RuntimePaths(
        data_dir=data_dir,
        config_dir=config_dir,
        cache_dir=cache_dir,
        logs_dir=data_dir / "logs",
        imports_dir=data_dir / "imports",
        credentials_dir=config_dir / "credentials",
        instance_dir=data_dir / "instance",
    )


def configure_desktop_environment():
    paths = get_runtime_paths().ensure()
    defaults = {
        "AIOS_DESKTOP": "1",
        "AIOS_DATA_DIR": str(paths.data_dir),
        "DATABASE_URL": f"sqlite:///{(paths.data_dir / 'aios_assistant.db').as_posix()}",
        "AIOS_INSTANCE_PATH": str(paths.instance_dir),
        "MEMORY_VECTOR_PATH": str(paths.data_dir / "memory_vectors"),
        "JOB_PORTAL_IMPORT_DIR": str(paths.imports_dir / "job_portals"),
        "HACKATHON_IMPORT_DIR": str(paths.imports_dir / "hackathons"),
        "WATCH_IMPORT_DIR": str(paths.imports_dir / "watch"),
        "AIOS_WORKER_STATE_PATH": str(paths.data_dir / "worker-state.json"),
        "AIOS_WATCH_STATE_PATH": str(paths.data_dir / "watch-state.json"),
        "AIOS_WORKERS_STATE_PATH": str(paths.data_dir / "workers.json"),
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    return paths
