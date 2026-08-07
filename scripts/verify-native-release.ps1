param(
    [string]$ReleaseDirectory = "",
    [switch]$RequireSigned
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$release = if ($ReleaseDirectory) {
    [System.IO.Path]::GetFullPath($ReleaseDirectory)
} else {
    Join-Path $repo "release\windows-native"
}

if (-not (Test-Path -LiteralPath $release -PathType Container)) {
    throw "Release directory was not found: $release"
}

$manifestPath = Join-Path $release "build-manifest.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "build-manifest.json is missing from $release"
}

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()
$warnings = [System.Collections.Generic.List[string]]::new()

if ([string]::IsNullOrWhiteSpace([string]$manifest.sourceCommit)) {
    $failures.Add("Manifest does not record the source commit.")
}
if ($manifest.sourceTreeDirty -eq $true) {
    $warnings.Add("Bundle was built from a dirty source tree.")
}

foreach ($entry in @($manifest.files)) {
    $relative = [string]$entry.path
    $path = Join-Path $release ($relative -replace '/', '\')
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $failures.Add("Missing manifest file: $relative")
        continue
    }
    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
    $expected = ([string]$entry.sha256).ToUpperInvariant()
    if ($actual -ne $expected) {
        $failures.Add("Hash mismatch: $relative")
    }
    $bytesMatch = ((Get-Item -LiteralPath $path).Length -eq [int64]$entry.bytes)
    if (-not $bytesMatch) {
        $failures.Add("Size mismatch: $relative")
    }
    $checks.Add([ordered]@{
        path = $relative
        hash_matches = ($actual -eq $expected)
        bytes_match = $bytesMatch
    })
}

foreach ($required in @("AiOS-Core.exe", "aios_assistant.exe", "build-manifest.json", "SHA256SUMS.txt", "SIGNING_STATUS.txt")) {
    if (-not (Test-Path -LiteralPath (Join-Path $release $required) -PathType Leaf)) {
        $failures.Add("Required release file is missing: $required")
    }
}

$credentialFiles = Get-ChildItem -LiteralPath $release -File -Recurse | Where-Object {
    $_.Name -match "(?i)(google_client_secret|client_secret|oauth|token|\.env)"
}
if ($credentialFiles) {
    $failures.Add("Credential-like files were found in the release: $($credentialFiles.Name -join ', ')")
}

$signature = @{}
foreach ($binary in @("AiOS-Core.exe", "aios_assistant.exe")) {
    $binaryPath = Join-Path $release $binary
    if (Test-Path -LiteralPath $binaryPath) {
        $status = Get-AuthenticodeSignature -FilePath $binaryPath
        $signature[$binary] = $status.Status.ToString()
        if ($RequireSigned -and $status.Status -ne "Valid") {
            $failures.Add("Authenticode signature is not valid for $binary ($($status.Status)).")
        } elseif ($status.Status -ne "Valid") {
            $warnings.Add("Unsigned developer binary: $binary")
        }
    }
}

$ok = $failures.Count -eq 0
[ordered]@{
    ok = $ok
    release_directory = $release
    platform = $manifest.platform
    built_at = $manifest.builtAt
    files_checked = $checks.Count
    signatures = $signature
    warnings = @($warnings)
    failures = @($failures)
} | ConvertTo-Json -Depth 6

if (-not $ok) { exit 1 }
