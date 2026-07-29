# AiOS Native Windows Client

Flutter owns the Windows UI. `AiOS-Core.exe` runs the private Gmail, planning,
SQLite, Ollama, and background-worker services beside it on loopback only.

## Develop

```powershell
C:\Users\anura\development\flutter\bin\flutter.bat run -d windows
```

For a working local API during development, place a built `AiOS-Core.exe` next
to the Flutter executable or at `..\dist\AiOS-Core.exe`.

## Verify

```powershell
C:\Users\anura\development\flutter\bin\flutter.bat analyze
C:\Users\anura\development\flutter\bin\flutter.bat test
C:\Users\anura\development\flutter\bin\flutter.bat build windows --release
```

Use `..\scripts\build-windows-native.ps1` to produce the complete distributable
with the native client, local core, installer, and uninstaller.
