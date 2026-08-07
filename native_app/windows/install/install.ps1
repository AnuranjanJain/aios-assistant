param(
  [string]$InstallDirectory = "",
  [switch]$NoLaunch,
  [switch]$NoShortcuts,
  [switch]$NoRegistry
)

$ErrorActionPreference = "Stop"

$nativeRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$builtRelease = Join-Path $nativeRoot "build\windows\x64\runner\Release"
$sourceDir = if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "aios_assistant.exe")) {
  $PSScriptRoot
} else {
  $builtRelease
}
$exeName = "aios_assistant.exe"
$sourceExe = Join-Path $sourceDir $exeName
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
$installedExe = Join-Path $installDir $exeName
$desktopShortcut = if ($NoShortcuts) { Join-Path $installDir "_desktop\AiOS Assistant.lnk" } else { Join-Path ([Environment]::GetFolderPath("Desktop")) "AiOS Assistant.lnk" }
$startMenuDir = if ($NoShortcuts) { Join-Path $installDir "_start-menu" } else { Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs" }
$startMenuShortcut = Join-Path $startMenuDir "AiOS Assistant.lnk"
$legacyStartMenuDir = Join-Path $startMenuDir "AiOS Assistant"
$startupLauncher = Join-Path $startMenuDir "Startup\AiOS Assistant Startup.cmd"
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AiOS Assistant Native"
$oldUninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AiOS Assistant"

if (-not (Test-Path -LiteralPath $sourceExe)) {
  throw "Native release not found. Run scripts\build-windows-native.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $sourceDir "AiOS-Core.exe"))) {
  throw "AiOS-Core.exe is missing from the native release."
}

$managedRoots = @($sourceDir, $installDir) | ForEach-Object {
  [System.IO.Path]::GetFullPath($_).TrimEnd('\') + '\'
}
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object {
    $process = $_
    $process.Name -in @("aios_assistant.exe", "AiOS-Core.exe", "AiOS-Assistant.exe") -and
      $process.ExecutablePath -and
      ($managedRoots | Where-Object {
        $process.ExecutablePath.StartsWith($_, [System.StringComparison]::OrdinalIgnoreCase)
      }).Count -gt 0
  } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 500

Remove-Item -LiteralPath $installDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $legacyStartMenuDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Get-ChildItem -LiteralPath $sourceDir | Where-Object { $_.Name -ne "install.ps1" } | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $installDir -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall.ps1") -Destination $installDir -Force

$installedUninstaller = Join-Path $installDir "uninstall.ps1"
if (-not $NoShortcuts) {
  $shell = New-Object -ComObject WScript.Shell
  foreach ($shortcutPath in @($desktopShortcut, $startMenuShortcut)) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $installedExe
    $shortcut.WorkingDirectory = $installDir
    $shortcut.IconLocation = "$installedExe,0"
    $shortcut.Description = "AiOS Assistant - private local life OS"
    $shortcut.Save()
  }
}

# Preserve an existing startup preference while moving it to the native app.
if (-not $NoShortcuts -and (Test-Path -LiteralPath $startupLauncher)) {
  @(
    "@echo off",
    "start `"`" /min `"$installedExe`" --hidden"
  ) | Set-Content -LiteralPath $startupLauncher -Encoding Ascii
}

if (-not $NoRegistry) {
  Remove-Item -LiteralPath $oldUninstallKey -Recurse -Force -ErrorAction SilentlyContinue
  New-Item -Path $uninstallKey -Force | Out-Null
  New-ItemProperty -Path $uninstallKey -Name "DisplayName" -Value "AiOS Assistant" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $uninstallKey -Name "DisplayVersion" -Value "0.3.0" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $uninstallKey -Name "Publisher" -Value "Anu Ranjan" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $uninstallKey -Name "DisplayIcon" -Value $installedExe -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $uninstallKey -Name "InstallLocation" -Value $installDir -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $uninstallKey -Name "UninstallString" -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$installedUninstaller`"" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $uninstallKey -Name "NoModify" -Value 1 -PropertyType DWord -Force | Out-Null
  New-ItemProperty -Path $uninstallKey -Name "NoRepair" -Value 1 -PropertyType DWord -Force | Out-Null
}

if (-not $NoLaunch) {
  Start-Process -FilePath $installedExe -WorkingDirectory $installDir
  Write-Output "Installed and launched: $installedExe"
} else {
  Write-Output "Installed without launch: $installedExe"
}
