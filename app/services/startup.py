import os
import shlex
import subprocess
import sys
from pathlib import Path

from app.services.settings import get_setting, set_setting


STARTUP_ENABLED_KEY = "STARTUP_ENABLED"
STARTUP_ENTRY_NAME = "AiOS Assistant Startup"
CORE_DESKTOP_SERVICES = (
    "Reminder service",
    "Import watcher",
    "Opportunity monitor",
    "Desktop activity tracker",
)


def project_root():
    return Path(__file__).resolve().parents[2]


def installed_executable_path():
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Local" / "Programs" / "AiOS Assistant" / "AiOS-Assistant.exe"
    if sys.platform.startswith("linux"):
        return Path.home() / ".local" / "bin" / "AiOS-Assistant"
    return None


def app_command():
    installed = installed_executable_path()
    if installed and installed.exists():
        return [str(installed)]

    if getattr(sys, "frozen", False):
        return [sys.executable]

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = str(pythonw if sys.platform == "win32" and pythonw.exists() else Path(sys.executable))
    return [executable, str(project_root() / "desktop_app.py")]


def startup_enabled_setting():
    return get_setting(STARTUP_ENABLED_KEY, "0") == "1"


def startup_entry_path():
    if sys.platform == "win32":
        appdata = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
        return (
            appdata
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / f"{STARTUP_ENTRY_NAME}.cmd"
        )

    if sys.platform.startswith("linux"):
        return Path.home() / ".config" / "autostart" / "aios-assistant.desktop"

    return None


def startup_supported():
    return startup_entry_path() is not None


def startup_entry_installed():
    path = startup_entry_path()
    return bool(path and path.exists())


def _windows_start_line(command):
    return f'start "" /min {subprocess.list2cmdline(command)}'


def build_windows_launcher():
    command = app_command()
    lines = [
        "@echo off",
        "set AIOS_START_PATH=/",
        _windows_start_line(command),
    ]
    return "\r\n".join(lines) + "\r\n"


def build_linux_launcher():
    command = app_command()
    commands = [f"AIOS_START_PATH=/ {shlex.join(command)} >/dev/null 2>&1 &"]
    shell_command = " ".join(commands)
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Name=AiOS Assistant",
            f"Exec=sh -lc {shlex.quote(shell_command)}",
            "Terminal=false",
            "X-GNOME-Autostart-enabled=true",
            "",
        ]
    )


def build_startup_launcher():
    if sys.platform == "win32":
        return build_windows_launcher()
    if sys.platform.startswith("linux"):
        return build_linux_launcher()
    return ""


def install_startup_entry():
    path = startup_entry_path()
    if path is None:
        return {"status": "unsupported", "message": "Startup is not supported on this OS yet."}

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_startup_launcher(), encoding="utf-8")
    return {"status": "enabled", "message": f"Startup launcher installed at {path}", "path": str(path)}


def remove_startup_entry():
    path = startup_entry_path()
    if path and path.exists():
        path.unlink()
    return {"status": "disabled", "message": "Startup launcher removed.", "path": str(path) if path else ""}


def save_startup_settings(form):
    enabled = form.get("startup_enabled") == "1"

    set_setting(STARTUP_ENABLED_KEY, "1" if enabled else "0")

    if enabled:
        return install_startup_entry()
    return remove_startup_entry()


def startup_overview():
    path = startup_entry_path()
    installed = installed_executable_path()
    return {
        "supported": startup_supported(),
        "enabled": startup_enabled_setting(),
        "installed": startup_entry_installed(),
        "path": str(path) if path else "",
        "app_command": " ".join(app_command()),
        "app_installed": bool(installed and installed.exists()),
        "install_path": str(installed) if installed else "",
        "platform": "Windows" if sys.platform == "win32" else ("Linux" if sys.platform.startswith("linux") else sys.platform),
        "core_services": CORE_DESKTOP_SERVICES,
    }
