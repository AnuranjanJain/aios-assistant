import os
import shutil
import subprocess
import sys

from automation_agent.tools.base import ToolResult


class DesktopTools:
    """Explicit foreground UI controls. Disabled unless the user opts in."""

    def __init__(self):
        self.enabled = os.getenv("AIOS_DESKTOP_CONTROL_ENABLED", "") == "1"

    def execute(self, operation, arguments):
        if not self.enabled:
            raise PermissionError(
                "Foreground desktop control is disabled. Set AIOS_DESKTOP_CONTROL_ENABLED=1 to opt in."
            )
        handler = getattr(self, operation, None)
        if handler is None or operation.startswith("_"):
            raise ValueError(f"Unsupported desktop operation: {operation}")
        return handler(**arguments)

    def click(self, x, y):
        if sys.platform == "win32":
            import pyautogui

            pyautogui.click(int(x), int(y))
        else:
            xdotool = shutil.which("xdotool")
            if not xdotool:
                raise RuntimeError("xdotool is not installed.")
            subprocess.run(
                [xdotool, "mousemove", str(int(x)), str(int(y)), "click", "1"],
                check=True,
                timeout=10,
            )
        return ToolResult(True, f"Clicked at {int(x)}, {int(y)}.")

    def type_text(self, text):
        if len(text) > 2000:
            raise ValueError("Desktop typing is limited to 2,000 characters per action.")
        if sys.platform == "win32":
            import pyautogui

            pyautogui.write(text, interval=0.01)
        else:
            xdotool = shutil.which("xdotool")
            if not xdotool:
                raise RuntimeError("xdotool is not installed.")
            subprocess.run([xdotool, "type", "--", text], check=True, timeout=30)
        return ToolResult(True, f"Typed {len(text)} characters into the active window.")
