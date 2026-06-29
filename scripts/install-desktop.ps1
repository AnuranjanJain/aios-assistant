param(
    [string]$SourceExe = "",
    [switch]$EnableStartup,
    [switch]$NoDesktopShortcut
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot

if (-not $SourceExe) {
    $candidates = @(
        (Join-Path $repo "release\windows\AiOS-Assistant.exe"),
        (Join-Path $repo "release\AiOS-Assistant.exe"),
        (Join-Path $repo "dist\AiOS-Assistant.exe")
    )
    $SourceExe = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $SourceExe -or -not (Test-Path $SourceExe)) {
    throw "AiOS-Assistant.exe was not found. Build it with scripts\build-desktop.ps1 first."
}

$installDir = Join-Path $env:LOCALAPPDATA "Programs\AiOS Assistant"
$installExe = Join-Path $installDir "AiOS-Assistant.exe"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\AiOS Assistant"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "AiOS Assistant.lnk"
$startMenuShortcut = Join-Path $startMenuDir "AiOS Assistant.lnk"
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$startupShortcut = Join-Path $startupDir "AiOS Assistant.lnk"
$startupLauncher = Join-Path $startupDir "AiOS Assistant Startup.cmd"

New-Item -ItemType Directory -Force -Path $installDir | Out-Null
New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
Copy-Item -LiteralPath $SourceExe -Destination $installExe -Force

$shell = New-Object -ComObject WScript.Shell

function New-AiOSShortcut {
    param(
        [string]$Path,
        [string]$Target,
        [string]$Description
    )

    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $Target
    $shortcut.WorkingDirectory = Split-Path -Parent $Target
    $shortcut.Description = $Description
    $shortcut.IconLocation = "$Target,0"
    $shortcut.Save()
}

New-AiOSShortcut -Path $startMenuShortcut -Target $installExe -Description "AiOS local-first desktop agent"

if (-not $NoDesktopShortcut) {
    New-AiOSShortcut -Path $desktopShortcut -Target $installExe -Description "AiOS local-first desktop agent"
}

if ($EnableStartup) {
    New-Item -ItemType Directory -Force -Path $startupDir | Out-Null
    if (Test-Path $startupShortcut) {
        Remove-Item -LiteralPath $startupShortcut -Force
    }
    @(
        "@echo off",
        "set AIOS_START_PATH=/",
        "start """" /min ""$installExe"""
    ) | Set-Content -Path $startupLauncher -Encoding ASCII
}

$installInfo = @{
    installedAt = (Get-Date).ToString("o")
    executable = $installExe
    startMenuShortcut = $startMenuShortcut
    desktopShortcut = if ($NoDesktopShortcut) { "" } else { $desktopShortcut }
    startupShortcut = if ($EnableStartup) { $startupLauncher } else { "" }
} | ConvertTo-Json -Depth 3

$installInfo | Set-Content -Path (Join-Path $installDir "install.json") -Encoding UTF8

Write-Host "AiOS Assistant installed to $installExe"
Write-Host "Start Menu shortcut: $startMenuShortcut"
if (-not $NoDesktopShortcut) {
    Write-Host "Desktop shortcut: $desktopShortcut"
}
if ($EnableStartup) {
    Write-Host "Startup launcher: $startupLauncher"
}
