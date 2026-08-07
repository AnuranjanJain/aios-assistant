param(
    [string]$ReleaseDir = ""
)

$ErrorActionPreference = "Stop"

if (-not $ReleaseDir) {
    $ReleaseDir = Join-Path (Split-Path -Parent $PSScriptRoot) "release\windows-native"
}
$release = (Resolve-Path -LiteralPath $ReleaseDir).Path
$installer = Join-Path $release "install.ps1"
$uninstaller = Join-Path $release "uninstall.ps1"
foreach ($required in @($installer, $uninstaller, (Join-Path $release "aios_assistant.exe"), (Join-Path $release "AiOS-Core.exe"))) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Native release file is missing: $required"
    }
}

$tempRoot = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
$installDir = Join-Path $env:TEMP ("aios-installer-smoke-" + [Guid]::NewGuid().ToString("N"))
if (-not $installDir.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Installer smoke target escaped the temporary directory."
}

try {
    & $installer -InstallDirectory $installDir -NoLaunch -NoShortcuts -NoRegistry
    foreach ($required in @("aios_assistant.exe", "AiOS-Core.exe", "flutter_windows.dll", "data\flutter_assets")) {
        if (-not (Test-Path -LiteralPath (Join-Path $installDir $required))) {
            throw "Installed payload is missing: $required"
        }
    }
    $firstCoreHash = (Get-FileHash -LiteralPath (Join-Path $installDir "AiOS-Core.exe") -Algorithm SHA256).Hash
    & $installer -InstallDirectory $installDir -NoLaunch -NoShortcuts -NoRegistry
    $secondCoreHash = (Get-FileHash -LiteralPath (Join-Path $installDir "AiOS-Core.exe") -Algorithm SHA256).Hash
    if ($firstCoreHash -ne $secondCoreHash) {
        throw "Installer upgrade changed the core payload unexpectedly."
    }
    & (Join-Path $installDir "uninstall.ps1") -InstallDirectory $installDir -NoShortcuts -NoRegistry
    if (Test-Path -LiteralPath $installDir) {
        throw "Installer cleanup left the temporary directory behind: $installDir"
    }
    [ordered]@{
        ok = $true
        installed_payload = @("aios_assistant.exe", "AiOS-Core.exe", "flutter_windows.dll", "data\flutter_assets")
        upgrade = $true
        cleanup = $true
    } | ConvertTo-Json
} finally {
    if (Test-Path -LiteralPath $installDir) {
        & $uninstaller -InstallDirectory $installDir -NoShortcuts -NoRegistry
    }
}
