import hashlib
import json
import shutil
import tarfile
import uuid
import zipfile
from collections import defaultdict
from pathlib import Path

from automation_agent.tools.base import ToolResult


CATEGORIES = {
    "Images": {".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".svg", ".webp"},
    "Videos": {".avi", ".mkv", ".mov", ".mp4", ".webm"},
    "Documents": {".csv", ".doc", ".docx", ".md", ".pdf", ".ppt", ".pptx", ".txt", ".xls", ".xlsx"},
    "Archives": {".7z", ".gz", ".rar", ".tar", ".tgz", ".zip"},
    "Projects": {".code-workspace", ".ipynb", ".java", ".js", ".py", ".rs", ".ts"},
}


class FileTools:
    def __init__(self, config, safety):
        self.config = config
        self.safety = safety

    def execute(self, operation, arguments):
        handler = getattr(self, operation, None)
        if handler is None:
            raise ValueError(f"Unsupported file operation: {operation}")
        return handler(**arguments)

    def organize_folder(self, source):
        source_path = self.safety.validate_path(source, must_exist=True)
        files = [item for item in source_path.iterdir() if item.is_file()]
        self.safety.validate_batch(files)
        changed = []
        counts = defaultdict(int)
        for item in files:
            category = self._category(item)
            destination_dir = source_path / category
            destination_dir.mkdir(exist_ok=True)
            destination = self._unique_destination(destination_dir / item.name)
            shutil.move(str(item), destination)
            changed.append(str(destination))
            counts[category] += 1
        return ToolResult(
            True,
            f"Organized {len(changed)} files in {source_path.name}.",
            changed,
            {"counts": dict(counts)},
        )

    def create_folders(self, parent, names):
        parent_path = self.safety.validate_path(parent, must_exist=True)
        changed = []
        for name in names:
            safe_name = "".join(character for character in str(name).strip() if character not in '<>:"/\\|?*')
            if not safe_name:
                continue
            folder = self.safety.validate_path(parent_path / safe_name)
            folder.mkdir(parents=False, exist_ok=True)
            changed.append(str(folder))
        return ToolResult(True, f"Created {len(changed)} folders.", changed)

    def move(self, source, destination):
        source_path = self.safety.validate_path(source, must_exist=True)
        destination_path = self.safety.validate_path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(destination_path))
        return ToolResult(True, f"Moved {source_path.name}.", [str(destination_path)])

    def rename(self, source, new_name):
        source_path = self.safety.validate_path(source, must_exist=True)
        destination = self.safety.validate_path(source_path.with_name(new_name))
        source_path.rename(destination)
        return ToolResult(True, f"Renamed {source_path.name} to {destination.name}.", [str(destination)])

    def quarantine(self, source):
        source_path = self.safety.validate_path(source, must_exist=True)
        quarantine_id = uuid.uuid4().hex
        target_dir = self.config.data_dir / "quarantine" / quarantine_id
        target_dir.mkdir(parents=True)
        destination = target_dir / source_path.name
        shutil.move(str(source_path), str(destination))
        manifest = {"original": str(source_path), "quarantined": str(destination)}
        (target_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return ToolResult(
            True,
            f"Moved {source_path.name} to AiOS quarantine.",
            [str(destination)],
            manifest,
            reversible=True,
        )

    def restore(self, quarantined, original):
        quarantined_path = Path(quarantined).resolve(strict=True)
        quarantine_root = (self.config.data_dir / "quarantine").resolve()
        if quarantine_root not in quarantined_path.parents:
            raise ValueError("Restore source is not in AiOS quarantine.")
        original_path = self.safety.validate_path(original)
        original_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(quarantined_path), str(original_path))
        return ToolResult(True, f"Restored {original_path.name}.", [str(original_path)])

    def find_duplicates(self, source):
        source_path = self.safety.validate_path(source, must_exist=True)
        files = [item for item in source_path.rglob("*") if item.is_file()]
        self.safety.validate_batch(files)
        by_size = defaultdict(list)
        for item in files:
            by_size[item.stat().st_size].append(item)
        by_hash = defaultdict(list)
        for group in by_size.values():
            if len(group) < 2:
                continue
            for item in group:
                digest = hashlib.sha256()
                with item.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                by_hash[digest.hexdigest()].append(str(item))
        duplicates = [group for group in by_hash.values() if len(group) > 1]
        return ToolResult(True, f"Found {len(duplicates)} duplicate groups.", data={"groups": duplicates})

    def compress(self, source, destination):
        source_path = self.safety.validate_path(source, must_exist=True)
        destination_path = self.safety.validate_path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        base = destination_path.with_suffix("")
        archive = shutil.make_archive(str(base), "zip", root_dir=source_path.parent, base_dir=source_path.name)
        return ToolResult(True, f"Created {Path(archive).name}.", [archive])

    def extract(self, source, destination):
        source_path = self.safety.validate_path(source, must_exist=True)
        destination_path = self.safety.validate_path(destination)
        destination_path.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(source_path):
            with zipfile.ZipFile(source_path) as archive:
                members = archive.infolist()
                total_size = sum(member.file_size for member in members)
                self._validate_archive_members(destination_path, [member.filename for member in members], total_size)
                archive.extractall(destination_path)
        elif tarfile.is_tarfile(source_path):
            with tarfile.open(source_path) as archive:
                members = archive.getmembers()
                total_size = sum(member.size for member in members)
                self._validate_archive_members(destination_path, [member.name for member in members], total_size)
                archive.extractall(destination_path, filter="data")
        else:
            raise ValueError("Only ZIP and TAR-compatible archives are supported in the MVP.")
        return ToolResult(True, f"Extracted {source_path.name}.", [str(destination_path)])

    def _validate_archive_members(self, destination, names, total_size):
        if len(names) > self.config.max_batch_files:
            raise ValueError("Archive contains too many entries.")
        if total_size > self.config.max_extract_bytes:
            raise ValueError("Archive exceeds the configured extraction size limit.")
        for name in names:
            member = (destination / name).resolve()
            if destination.resolve() not in member.parents and member != destination.resolve():
                raise ValueError("Archive contains an unsafe path.")

    @staticmethod
    def _category(path):
        for category, suffixes in CATEGORIES.items():
            if path.suffix.lower() in suffixes:
                return category
        return "Other"

    @staticmethod
    def _unique_destination(destination):
        if not destination.exists():
            return destination
        for counter in range(1, 10_000):
            candidate = destination.with_name(f"{destination.stem}-{counter}{destination.suffix}")
            if not candidate.exists():
                return candidate
        raise ValueError(f"Could not create a unique filename for {destination.name}.")
