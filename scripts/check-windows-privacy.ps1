param(
    [string[]]$Paths = @(
        "$env:LOCALAPPDATA\AiOS Assistant",
        "$env:APPDATA\AiOS Assistant",
        "$env:LOCALAPPDATA\Programs\AiOS Assistant"
    ),
    [switch]$RequireNoBroadWrite
)

$ErrorActionPreference = "Stop"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$broadNames = @(
    "Everyone",
    "BUILTIN\Users",
    "NT AUTHORITY\Authenticated Users",
    "NT AUTHORITY\INTERACTIVE"
)
$checks = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[string]]::new()

foreach ($rawPath in $Paths) {
    if ([string]::IsNullOrWhiteSpace($rawPath)) { continue }
    $path = [System.IO.Path]::GetFullPath($rawPath)
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        $checks.Add([ordered]@{ path = $path; exists = $false; owner = $null; broad_write = $false })
        continue
    }
    $acl = Get-Acl -LiteralPath $path
    $broadWrite = @($acl.Access | Where-Object {
        $identity = $_.IdentityReference.Value
        ($broadNames -contains $identity) -and
        ($_.AccessControlType -eq "Allow") -and
        (($_.FileSystemRights.ToString() -match "Write|Modify|FullControl|Delete"))
    })
    $ownerIsUser = $acl.Owner -eq $currentUser
    if (-not $ownerIsUser) {
        $failures.Add("Unexpected owner for ${path}: $($acl.Owner)")
    }
    if ($broadWrite.Count -gt 0) {
        $failures.Add("Broad write access found for ${path}: $($broadWrite.IdentityReference -join ', ')")
    }
    $checks.Add([ordered]@{
        path = $path
        exists = $true
        owner = $acl.Owner
        owner_is_current_user = $ownerIsUser
        broad_write = ($broadWrite.Count -gt 0)
    })
}

$ok = $failures.Count -eq 0
[ordered]@{
    ok = $ok
    current_user = $currentUser
    checks = @($checks)
    failures = @($failures)
    note = "This verifies the current Windows account only; clean-account Credential Manager and retention review remain release evidence."
} | ConvertTo-Json -Depth 6

if (-not $ok -and $RequireNoBroadWrite) { exit 1 }
