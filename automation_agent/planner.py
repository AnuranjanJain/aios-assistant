import re
import uuid
from pathlib import Path


class IntentError(ValueError):
    pass


class TaskPlanner:
    def __init__(self, config, safety):
        self.config = config
        self.safety = safety

    def create(self, request_text, parameters=None):
        parameters = dict(parameters or {})
        text = (request_text or "").strip()
        if not text:
            raise IntentError("Describe the task you want AiOS to perform.")

        lowered = text.lower()
        target = parameters.get("source") or parameters.get("target") or self._path_from_text(text)
        actions = []
        intent = "unknown"
        risk = "medium"

        if "organize" in lowered and ("folder" in lowered or "downloads" in lowered):
            intent = "organize_folder"
            target = target or str(Path.home() / "Downloads")
            actions.append(self._action("files", "organize_folder", {"source": target}))
        elif "duplicate" in lowered:
            intent = "find_duplicates"
            target = target or str(Path.home() / "Downloads")
            actions.append(self._action("files", "find_duplicates", {"source": target}))
            risk = "low"
        elif "create folder" in lowered:
            intent = "create_folders"
            parent = parameters.get("parent") or target or str(Path.home() / "Documents")
            names = parameters.get("names") or self._folder_names(text)
            if not names:
                raise IntentError("Provide folder names, separated by commas.")
            actions.append(self._action("files", "create_folders", {"parent": parent, "names": names}))
        elif "convert" in lowered and ("docx" in lowered or "document" in lowered) and "pdf" in lowered:
            intent = "convert_docx_to_pdf"
            source_dir = Path(target or Path.home() / "Documents")
            output_dir = parameters.get("destination") or str(source_dir / "PDF")
            files = sorted(source_dir.glob("*.docx"))
            if not files:
                raise IntentError(f"No DOCX files were found in {source_dir}.")
            self.safety.validate_batch(files)
            actions.extend(
                self._action("office", "convert_to_pdf", {"source": str(path), "destination_dir": output_dir})
                for path in files
            )
        elif "weekly report" in lowered and ("excel" in lowered or "spreadsheet" in lowered):
            intent = "weekly_excel_report"
            source = target or str(Path.home() / "Documents")
            destination = parameters.get("destination") or str(Path.home() / "Documents" / "Weekly Report.docx")
            actions.append(
                self._action(
                    "office",
                    "weekly_excel_report",
                    {"source": source, "destination": destination},
                )
            )
        elif "create" in lowered and "docx" in lowered:
            intent = "create_document"
            destination = parameters.get("destination") or str(Path.home() / "Documents" / "AiOS Document.docx")
            title = parameters.get("title") or "AiOS Document"
            notes = parameters.get("notes") or text
            paragraphs = [line.strip() for line in notes.splitlines() if line.strip()]
            actions.append(
                self._action(
                    "office",
                    "create_docx",
                    {"destination": destination, "title": title, "paragraphs": paragraphs},
                )
            )
        elif "ppt" in lowered or "presentation" in lowered:
            intent = "create_presentation"
            destination = parameters.get("destination") or str(Path.home() / "Documents" / "AiOS Presentation.pptx")
            title = parameters.get("title") or "AiOS Presentation"
            notes = parameters.get("notes") or text
            slides = parameters.get("slides") or self._slides_from_notes(title, notes)
            actions.append(
                self._action(
                    "office",
                    "create_pptx",
                    {"destination": destination, "title": title, "slides": slides},
                )
            )
        elif "screenshot" in lowered or "ocr" in lowered:
            intent = "analyze_screenshot"
            if not target:
                raise IntentError("Provide the screenshot path.")
            actions.append(self._action("screenshot", "analyze", {"source": target}))
            risk = "low"
        elif "compress" in lowered or "zip" in lowered:
            intent = "compress"
            if not target:
                raise IntentError("Provide the folder path to compress.")
            destination = parameters.get("destination") or f"{target}.zip"
            actions.append(self._action("files", "compress", {"source": target, "destination": destination}))
        elif "extract" in lowered or "unzip" in lowered:
            intent = "extract"
            if not target:
                raise IntentError("Provide the archive path.")
            destination = parameters.get("destination") or str(Path(target).with_suffix(""))
            actions.append(self._action("files", "extract", {"source": target, "destination": destination}))
        elif "delete" in lowered or "remove" in lowered:
            intent = "quarantine"
            if not target:
                raise IntentError("Provide the file or folder path to move to quarantine.")
            actions.append(self._action("files", "quarantine", {"source": target}))
            risk = "high"
        else:
            raise IntentError(
                "I could not map that request to a safe local tool yet. Try organize, duplicates, folders, DOCX to PDF, PPT, screenshot, compress, extract, or delete."
            )

        for action in actions:
            self._validate_action_paths(action)
        return {
            "id": uuid.uuid4().hex,
            "request": text,
            "intent": intent,
            "risk_level": risk,
            "actions": actions,
        }

    def _validate_action_paths(self, action):
        for key in ("source", "target", "parent", "destination", "destination_dir"):
            if action["arguments"].get(key):
                self.safety.validate_path(
                    action["arguments"][key],
                    must_exist=key == "source" and action["operation"] not in {"create_docx", "create_pptx"},
                )

    @staticmethod
    def _action(tool, operation, arguments):
        return {"id": uuid.uuid4().hex, "tool": tool, "operation": operation, "arguments": arguments}

    @staticmethod
    def _path_from_text(text):
        quoted = re.findall(r'["\']([^"\']+)["\']', text)
        if quoted:
            return quoted[0]
        windows = re.search(r"([A-Za-z]:\\[^\r\n,;]+)", text)
        return windows.group(1).strip() if windows else None

    @staticmethod
    def _folder_names(text):
        match = re.search(r"(?:subjects?|folders?)\s*[:\-]\s*(.+)$", text, re.IGNORECASE)
        if not match:
            return []
        return [name.strip() for name in match.group(1).split(",") if name.strip()]

    @staticmethod
    def _slides_from_notes(title, notes):
        points = [point.strip(" -*\t") for point in re.split(r"[\r\n]+", notes) if point.strip()]
        return [
            {"title": title, "bullets": ["Generated locally by AiOS"]},
            {"title": "Notes", "bullets": points[:8] or [notes[:400]]},
        ]
