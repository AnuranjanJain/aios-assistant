$ErrorActionPreference = "Stop"

$installDir = Join-Path $env:LOCALAPPDATA "Programs\AiOS Assistant"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "AiOS Assistant.lnk"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$startMenuShortcut = Join-Path $startMenuDir "AiOS Assistant.lnk"
$startupLauncher = Join-Path $startMenuDir "Startup\AiOS Assistant Startup.cmd"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AiOS Assistant Native"

Get-Process aios_assistant, AiOS-Core, AiOS-Assistant -ErrorAction SilentlyContinue |
  Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300

Remove-Item -LiteralPath $desktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startMenuShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startupLauncher -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $uninstallKey -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $installDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Output "AiOS Assistant was uninstalled. Local data was preserved in %APPDATA%\AiOS Assistant."
