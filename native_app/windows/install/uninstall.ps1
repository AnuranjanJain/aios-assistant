param(
  [string]$InstallDirectory = "",
  [switch]$NoShortcuts,
  [switch]$NoRegistry
)

$ErrorActionPreference = "Stop"

$installDir = if ($InstallDirectory) {
  [System.IO.Path]::GetFullPath($InstallDirectory)
} else {
  Join-Path $env:LOCALAPPDATA "Programs\AiOS Assistant"
}
if ($InstallDirectory) {
  $tempRoot = ([System.IO.Path]::GetFullPath($env:TEMP)).TrimEnd('\') + '\'
  if (-not $installDir.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "-InstallDirectory is reserved for isolated test installs under $env:TEMP."
  }
}
$desktopShortcut = if ($NoShortcuts) { Join-Path $installDir "_desktop\AiOS Assistant.lnk" } else { Join-Path ([Environment]::GetFolderPath("Desktop")) "AiOS Assistant.lnk" }
$startMenuDir = if ($NoShortcuts) { Join-Path $installDir "_start-menu" } else { Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs" }
$startMenuShortcut = Join-Path $startMenuDir "AiOS Assistant.lnk"
$legacyStartMenuDir = Join-Path $startMenuDir "AiOS Assistant"
$startupLauncher = Join-Path $startMenuDir "Startup\AiOS Assistant Startup.cmd"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AiOS Assistant Native"

$managedRoot = [System.IO.Path]::GetFullPath($installDir).TrimEnd('\') + '\'
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {
    $_.Name -in @("aios_assistant.exe", "AiOS-Core.exe", "AiOS-Assistant.exe") -and
      $_.ExecutablePath -and
      $_.ExecutablePath.StartsWith($managedRoot, [System.StringComparison]::OrdinalIgnoreCase)
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 300

if (-not $NoShortcuts) {
  Remove-Item -LiteralPath $desktopShortcut -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $startMenuShortcut -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $legacyStartMenuDir -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $startupLauncher -Force -ErrorAction SilentlyContinue
}
if (-not $NoRegistry) {
  Remove-Item -LiteralPath $uninstallKey -Recurse -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $installDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Output "AiOS Assistant was uninstalled. Local data was preserved in %APPDATA%\AiOS Assistant."
