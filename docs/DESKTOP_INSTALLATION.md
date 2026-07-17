# Desktop Installation

AiOS Assistant is a native Flutter Windows app backed by an adjacent headless
local core. It does not render the Flask website inside a desktop window.

## Windows

Build the executable:

```powershell
.\scripts\build-windows-native.ps1
```

Install it for the current user:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\native_app\windows\install\install.ps1
```

This creates:

```text
%LOCALAPPDATA%\Programs\AiOS Assistant\aios_assistant.exe
%LOCALAPPDATA%\Programs\AiOS Assistant\AiOS-Core.exe
%APPDATA%\Microsoft\Windows\Start Menu\Programs\AiOS Assistant.lnk
%USERPROFILE%\Desktop\AiOS Assistant.lnk
```

Enable **Open on Windows startup** from Settings to create a background tray
launcher. Closing or minimizing hides AiOS to the tray; use **Exit AiOS** in
Settings or the tray menu to stop the Flutter client and local core. The core
owns the background services:

- reminder service
- import watcher
- opportunity monitor
- desktop activity tracker

## Arch / Linux

Build the target package on Linux:

```bash
./scripts/build-desktop-arch.sh
```

Install it:

```bash
tar -xzf release/AiOS-Assistant-arch-x86_64.tar.gz -C /tmp/aios
/tmp/aios/install-arch.sh --enable-startup
```

The installer copies the binary to `$HOME/.local/bin/AiOS-Assistant`, registers the desktop entry, installs the icon, and optionally adds an autostart entry.

## Runtime Data

AiOS keeps app data outside the repo:

```text
Windows data:  %LOCALAPPDATA%\AiOS Assistant
Windows config:%APPDATA%\AiOS Assistant
Linux data:    $XDG_DATA_HOME/aios-assistant
Linux config:  $XDG_CONFIG_HOME/aios-assistant
```

Credentials, Gmail tokens, SQLite databases, logs, imports, and memory vectors stay local to those runtime folders.

For Gmail, open **Accounts** and select **Sign in with Google**, then approve
read-only access in the system browser. No keys or JSON files are required.
Connect each mailbox separately. See
[Gmail OAuth Setup](GMAIL_OAUTH_SETUP.md).
