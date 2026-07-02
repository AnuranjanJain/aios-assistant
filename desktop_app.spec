# Build on the target operating system:
#   python -m PyInstaller --clean --noconfirm desktop_app.spec

from PyInstaller.utils.hooks import collect_submodules


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
    datas=[
        ("app/templates", "app/templates"),
        ("app/static", "app/static"),
    ],
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
