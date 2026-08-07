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

Use `..\scripts\build-windows-native.ps1` (or set `AIOS_FLUTTER_PATH`) to produce the complete distributable
with the native client, local core, installer, and uninstaller.

The API bearer token is stored through `flutter_secure_storage` on Windows
(Windows Credential Manager); `native-settings.json` contains only non-secret
preferences. The release folder also includes `build-manifest.json`,
`SHA256SUMS.txt`, `sbom.cdx.json`, and `SIGNING_STATUS.txt`.
