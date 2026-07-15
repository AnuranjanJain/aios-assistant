# Desktop Installation

AiOS Assistant is installed as a local desktop app. The web routes are still used internally by the native shell, but the user-facing app is the packaged executable.

## Windows

Build the executable:

```powershell
.\scripts\build-desktop.ps1
```

Install it for the current user:

```powershell
.\scripts\install-desktop.ps1 -EnableStartup
```

This creates:

```text
%LOCALAPPDATA%\Programs\AiOS Assistant\AiOS-Assistant.exe
%APPDATA%\Microsoft\Windows\Start Menu\Programs\AiOS Assistant\AiOS Assistant.lnk
%USERPROFILE%\Desktop\AiOS Assistant.lnk
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AiOS Assistant Startup.cmd
```

The startup launcher starts the installed executable once in background tray
mode. Closing the native window hides AiOS to the tray; use **Exit AiOS** in
Settings or the tray menu to fully quit. The executable owns the background
services:

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

For Gmail, select **Sign in with Google** under **Settings -> Google
accounts**, then approve read-only access. No keys or JSON files are required.
Connect each mailbox separately. See
[Gmail OAuth Setup](GMAIL_OAUTH_SETUP.md).
