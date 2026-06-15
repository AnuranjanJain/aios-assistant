import shutil
from pathlib import Path

from runtime_paths import get_runtime_paths


def copy_file_if_missing(source, target):
    if not source.exists() or target.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def copy_tree_if_missing(source, target):
    copied = 0
    if not source.exists():
        return copied

    for path in source.rglob("*"):
        if not path.is_file():
            continue
        destination = target / path.relative_to(source)
        if copy_file_if_missing(path, destination):
            copied += 1
    return copied


def migrate_legacy_data(source_root):
    source_root = Path(source_root).resolve()
    paths = get_runtime_paths().ensure()
    copied_state = 0

    for candidate in (
        source_root / "instance" / "aios_assistant.db",
        source_root / "aios_assistant.db",
    ):
        if copy_file_if_missing(candidate, paths.data_dir / "aios_assistant.db"):
            copied_state += 1
            break

    credentials_count = copy_tree_if_missing(source_root / "credentials", paths.credentials_dir)
    imports_count = copy_tree_if_missing(source_root / "imports", paths.imports_dir)

    for source_name, target_name in {
        ".aios_worker_state.json": "worker-state.json",
        ".aios_watch_state.json": "watch-state.json",
        ".aios_workers.json": "workers.json",
    }.items():
        if copy_file_if_missing(source_root / source_name, paths.data_dir / target_name):
            copied_state += 1

    return {
        "data_dir": str(paths.data_dir),
        "config_dir": str(paths.config_dir),
        "state_files": copied_state,
        "credential_files": credentials_count,
        "import_files": imports_count,
    }
