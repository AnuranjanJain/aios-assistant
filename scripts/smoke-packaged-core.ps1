param(
    [string]$CorePath = "",
    [string]$CleanupPath = "",
    [switch]$KeepData
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
if ($CleanupPath) {
    $cleanupTarget = (Resolve-Path -LiteralPath $CleanupPath).Path
    $tempRoot = [System.IO.Path]::GetFullPath($env:TEMP)
    if (-not $cleanupTarget.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "CleanupPath must stay inside the Windows temporary directory."
    }
    Remove-Item -LiteralPath $cleanupTarget -Recurse -Force
    Write-Host "Removed $cleanupTarget"
    exit 0
}
if (-not $CorePath) {
    $CorePath = Join-Path $repo "release\windows-native\AiOS-Core.exe"
}
$CorePath = (Resolve-Path -LiteralPath $CorePath).Path
$smokeDir = Join-Path $env:TEMP ("aios-packaged-smoke-" + [Guid]::NewGuid().ToString("N"))
$secret = "packaged-smoke-" + [Guid]::NewGuid().ToString("N")
$process = $null

New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null
$env:AIOS_DATA_DIR = $smokeDir
$env:AIOS_NATIVE_PAIRING_SECRET = $secret
$env:AIOS_HEADLESS = "1"
$env:AIOS_START_HIDDEN = "1"

try {
    $process = Start-Process -FilePath $CorePath -ArgumentList @("--core-only") -WorkingDirectory (Split-Path -Parent $CorePath) -WindowStyle Hidden -PassThru
    $pairing = $null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        Start-Sleep -Milliseconds 500
        if ($process.HasExited) {
            throw "Packaged core exited before becoming ready (code $($process.ExitCode))."
        }
        try {
            $pairing = Invoke-RestMethod -Uri "http://127.0.0.1:5050/api/local/pairing" -Headers @{ "X-AiOS-Native-Pairing" = $secret } -TimeoutSec 2
            if ($pairing.api_token) { break }
        } catch {}
    }
    if (-not $pairing.api_token) {
        throw "Packaged core did not complete native pairing within 30 seconds."
    }

    $live = Invoke-RestMethod -Uri "http://127.0.0.1:5050/api/live" -Headers @{ "X-AiOS-Token" = $pairing.api_token } -TimeoutSec 5
    if (-not $live.updated_at -or $null -eq $live.plan) {
        throw "Packaged core live endpoint returned an incomplete response."
    }
    [ordered]@{
        ok = $true
        service = $pairing.service
        base_url = $pairing.base_url
        live_response_ok = [bool]$live.updated_at
        flutter = "packaged core smoke"
    } | ConvertTo-Json
}
finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $process.Id -Timeout 10 -ErrorAction SilentlyContinue
    }
    Get-Process -Name "AiOS-Core" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $CorePath } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Remove-Item Env:AIOS_DATA_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:AIOS_NATIVE_PAIRING_SECRET -ErrorAction SilentlyContinue
    Remove-Item Env:AIOS_HEADLESS -ErrorAction SilentlyContinue
    Remove-Item Env:AIOS_START_HIDDEN -ErrorAction SilentlyContinue
    if (-not $KeepData -and (Test-Path -LiteralPath $smokeDir)) {
        Start-Sleep -Seconds 2
        for ($cleanupAttempt = 0; $cleanupAttempt -lt 5; $cleanupAttempt++) {
            try {
                Remove-Item -LiteralPath $smokeDir -Recurse -Force -ErrorAction Stop
                break
            } catch {
                if ($cleanupAttempt -eq 4) { throw }
                Start-Sleep -Seconds 1
            }
        }
    } elseif ($KeepData) {
        Write-Host "Smoke data kept at $smokeDir"
    }
}
