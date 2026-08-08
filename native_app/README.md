# AiOS Native Windows Client

Flutter owns the Windows UI. `AiOS-Core.exe` runs the private Gmail, planning,
SQLite, Ollama, and background-worker services beside it on loopback only.

## Develop

```powershell
flutter run -d windows
```

For a working local API during development, place a built `AiOS-Core.exe` next
to the Flutter executable or at `..\dist\AiOS-Core.exe`.

## Verify

```powershell
flutter analyze
flutter test
flutter build windows --release
```

Windows requires Developer Mode for Flutter's plugin symlinks. Open
`start ms-settings:developers`, enable **Developer Mode**, then retry the
release build. The release script fails closed if Flutter exits unsuccessfully;
it never copies a stale native executable into a new archive.

Use `..\scripts\build-windows-native.ps1` (or set `AIOS_FLUTTER_PATH`) to produce the complete distributable
with the native client, local core, installer, and uninstaller.

Install with `native_app\windows\install\install.ps1 -EnableStartup` when the
local background services should start at Windows sign-in. This uses a
per-user Startup launcher and starts the packaged client in hidden mode; the
native Settings screen can change the preference later.

The API bearer token is stored through `flutter_secure_storage` on Windows
(Windows Credential Manager); `native-settings.json` contains only non-secret
preferences. The release folder also includes `build-manifest.json`,
`SHA256SUMS.txt`, `sbom.cdx.json`, and `SIGNING_STATUS.txt`.

Native Settings includes a local data inventory, secret-redacted export,
scoped purge confirmation, and operational-history retention controls.
