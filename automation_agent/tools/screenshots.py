import shutil
from pathlib import Path

from automation_agent.tools.base import ToolResult


class ScreenshotTools:
    def __init__(self, safety):
        self.safety = safety

    def analyze(self, source):
        from PIL import Image

        source_path = self.safety.validate_path(source, must_exist=True)
        with Image.open(source_path) as image:
            metadata = {"width": image.width, "height": image.height, "mode": image.mode}
        text = ""
        warning = ""
        if shutil.which("tesseract"):
            import pytesseract

            text = pytesseract.image_to_string(str(source_path)).strip()
        else:
            warning = "Tesseract OCR is unavailable; image metadata was analyzed without text extraction."
        lowered = text.lower()
        error_terms = [term for term in ("error", "failed", "exception", "access denied", "not found") if term in lowered]
        summary = f"Read {source_path.name} ({metadata['width']}x{metadata['height']})."
        return ToolResult(
            True,
            summary,
            data={"text": text, "possible_errors": error_terms, "warning": warning, **metadata},
        )
