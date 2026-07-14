# Build on the target operating system:
#   python -m PyInstaller --clean --noconfirm desktop_app.spec

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


oauth_candidates = [
    os.environ.get("AIOS_GOOGLE_OAUTH_BUNDLE", ""),
    str(Path(os.environ.get("APPDATA", "")) / "AiOS Assistant" / "credentials" / "google_client_secret.json"),
    "credentials/google_client_secret.json",
]
oauth_client = next((Path(path) for path in oauth_candidates if path and Path(path).is_file()), None)
datas = [
    ("app/templates", "app/templates"),
    ("app/static", "app/static"),
]
if oauth_client:
    datas.append((str(oauth_client), "app_credentials"))


hiddenimports = (
    collect_submodules("webview")
    + collect_submodules("pystray")
    + collect_submodules("googleapiclient")
    + collect_submodules("google_auth_oauthlib")
    + [
        "docx",
        "pptx",
        "openpyxl",
        "PIL.Image",
        "pytesseract",
        "pyautogui",
        "playwright",
        "playwright.sync_api",
        "career_agent",
        "career_agent.api",
        "desktop_activity_worker",
        "hackathon_monitor_worker",
        "local_worker",
        "watch_import_worker",
    ]
)

a = Analysis(
    ["desktop_app.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pandas", "scipy", "matplotlib", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AiOS-Assistant",
    icon="app/static/icons/aios-icon.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
