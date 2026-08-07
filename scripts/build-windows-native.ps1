param(
    [string]$FlutterPath = "",
    [string]$PythonCommand = "python",
    [string]$SignToolPath = "",
    [switch]$RequireSigning
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$flutter = $FlutterPath
if (-not $flutter) {
    $flutter = $env:AIOS_FLUTTER_PATH
}
if (-not $flutter) {
    $flutterCommand = Get-Command flutter.bat -ErrorAction SilentlyContinue
    if ($flutterCommand) {
        $flutter = $flutterCommand.Source
    }
}
$nativeDir = Join-Path $repo "native_app"
$releaseDir = Join-Path $nativeDir "build\windows\x64\runner\Release"
$outputDir = Join-Path $repo "release\windows-native"
$archive = Join-Path $repo "release\AiOS-Assistant-native-windows-x64.zip"

if (-not $flutter -or -not (Test-Path -LiteralPath $flutter)) {
    throw "Flutter was not found. Pass -FlutterPath or set AIOS_FLUTTER_PATH, or put flutter.bat on PATH."
}
Set-Location $repo
$ErrorActionPreference = "Continue"
& $PythonCommand -m pip install -r requirements-desktop.txt 2>&1
$pipExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($pipExitCode -ne 0) { throw "Desktop dependency installation failed with exit code $pipExitCode." }
$ErrorActionPreference = "Continue"
& $PythonCommand -m PyInstaller --clean --noconfirm aios_core.spec 2>&1
$pyInstallerExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($pyInstallerExitCode -ne 0) { throw "AiOS Core packaging failed with exit code $pyInstallerExitCode." }

Set-Location $nativeDir
$ErrorActionPreference = "Continue"
& $flutter build windows --release 2>&1
$flutterExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($flutterExitCode -ne 0) {
    throw "Flutter Windows build failed with exit code $flutterExitCode. Enable Windows Developer Mode for plugin symlink support, then retry."
}
Copy-Item -LiteralPath (Join-Path $repo "dist\AiOS-Core.exe") -Destination $releaseDir -Force

if (Test-Path -LiteralPath $outputDir) {
    Remove-Item -LiteralPath $outputDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
Get-ChildItem -LiteralPath $releaseDir | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $outputDir -Recurse -Force
}
Copy-Item -LiteralPath (Join-Path $nativeDir "windows\install\install.ps1") -Destination $outputDir -Force
Copy-Item -LiteralPath (Join-Path $nativeDir "windows\install\uninstall.ps1") -Destination $outputDir -Force

if (-not $SignToolPath) {
    $signToolCommand = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($signToolCommand) {
        $SignToolPath = $signToolCommand.Source
    }
}
if (-not $SignToolPath) {
    $signToolCandidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin\*\x64\signtool.exe"),
        (Join-Path $env:ProgramFiles "Windows Kits\10\bin\*\x64\signtool.exe")
    ) | ForEach-Object {
        Get-ChildItem -Path $_ -File -ErrorAction SilentlyContinue
    } | Sort-Object FullName -Descending
    if ($signToolCandidates) {
        $SignToolPath = $signToolCandidates[0].FullName
    }
}
$signedFiles = @()
if ($SignToolPath) {
    $certificateThumbprint = $env:AIOS_SIGN_CERT_THUMBPRINT
    if (-not $certificateThumbprint) {
        if ($RequireSigning) {
            throw "Signing was required but AIOS_SIGN_CERT_THUMBPRINT is not set."
        }
    } else {
        foreach ($binary in @("aios_assistant.exe", "AiOS-Core.exe")) {
            $binaryPath = Join-Path $outputDir $binary
            if (Test-Path -LiteralPath $binaryPath) {
                & $SignToolPath sign /sha1 $certificateThumbprint /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $binaryPath
                $signature = Get-AuthenticodeSignature -FilePath $binaryPath
                if ($signature.Status -ne "Valid") {
                    throw "Authenticode signature validation failed for $binaryPath ($($signature.Status))."
                }
                $signedFiles += $binary
            }
        }
    }
} elseif ($RequireSigning) {
    throw "Signing was required but signtool.exe was not found."
}
if ($signedFiles.Count) {
    "SIGNED release. Authenticode verified for: $($signedFiles -join ', ')." |
        Set-Content -LiteralPath (Join-Path $outputDir "SIGNING_STATUS.txt") -Encoding ASCII
} else {
    "UNSIGNED developer build. Set AIOS_SIGN_CERT_THUMBPRINT and provide signtool.exe for a public release." |
        Set-Content -LiteralPath (Join-Path $outputDir "SIGNING_STATUS.txt") -Encoding ASCII
}

$manifest = [ordered]@{
    builtAt = (Get-Date).ToUniversalTime().ToString("o")
    platform = "windows-x64"
    flutter = (& $flutter --version | Select-Object -First 1)
    python = (& $PythonCommand --version)
    sourceCommit = ""
    sourceTreeDirty = $false
    files = @(
        Get-ChildItem -LiteralPath $outputDir -File -Recurse | ForEach-Object {
            $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
            [ordered]@{ path = $_.FullName.Substring($outputDir.Length + 1); sha256 = $hash.Hash; bytes = $_.Length }
        }
    )
}
$sourceCommit = ((& git -C $repo rev-parse HEAD) | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($sourceCommit)) {
    throw "Could not record the source commit in the release manifest."
}
$sourceDirtyText = ((& git -C $repo status --porcelain) | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw "Could not inspect source-tree state for the release manifest." }
$manifest.sourceCommit = $sourceCommit
$manifest.sourceTreeDirty = -not [string]::IsNullOrWhiteSpace($sourceDirtyText)
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $outputDir "build-manifest.json") -Encoding UTF8
Get-ChildItem -LiteralPath $outputDir -File -Recurse | Get-FileHash -Algorithm SHA256 |
    ForEach-Object { "$($_.Hash)  $($_.Path.Substring($outputDir.Length + 1))" } |
    Set-Content -LiteralPath (Join-Path $outputDir "SHA256SUMS.txt") -Encoding ASCII

$pipAuditAvailable = & $PythonCommand -c "import importlib.util; print('1' if importlib.util.find_spec('pip_audit') else '0')"
if ($pipAuditAvailable -match "1") {
    $sbom = & $PythonCommand -m pip_audit -r (Join-Path $repo "requirements.txt") --format cyclonedx-json
    $auditExitCode = $LASTEXITCODE
    $sbom | Set-Content -LiteralPath (Join-Path $outputDir "sbom.cdx.json") -Encoding UTF8
    if ($auditExitCode -ne 0) { throw "Dependency SBOM generation failed with exit code $auditExitCode." }
}

if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $archive) | Out-Null
Compress-Archive -Path "$outputDir\*" -DestinationPath $archive
Write-Host "Built $archive"
