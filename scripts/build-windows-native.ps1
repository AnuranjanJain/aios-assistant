$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$flutter = "C:\Users\anura\development\flutter\bin\flutter.bat"
$oauthClient = Join-Path $env:APPDATA "AiOS Assistant\credentials\google_client_secret.json"
$stagedOAuthDir = Join-Path $repo "credentials"
$stagedOAuthClient = Join-Path $stagedOAuthDir "google_client_secret.json"
$nativeDir = Join-Path $repo "native_app"
$releaseDir = Join-Path $nativeDir "build\windows\x64\runner\Release"
$outputDir = Join-Path $repo "release\windows-native"
$archive = Join-Path $repo "release\AiOS-Assistant-native-windows-x64.zip"

if (-not (Test-Path -LiteralPath $flutter)) {
    throw "Flutter was not found at $flutter"
}
if (-not (Test-Path -LiteralPath $oauthClient)) {
    throw "Release OAuth client is missing at $oauthClient"
}

Set-Location $repo
python -m pip install -r requirements-desktop.txt
New-Item -ItemType Directory -Force -Path $stagedOAuthDir | Out-Null
Copy-Item -LiteralPath $oauthClient -Destination $stagedOAuthClient -Force
$env:AIOS_GOOGLE_OAUTH_BUNDLE = $stagedOAuthClient
python -m PyInstaller --clean --noconfirm aios_core.spec

Set-Location $nativeDir
& $flutter build windows --release
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

if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}
Compress-Archive -Path "$outputDir\*" -DestinationPath $archive
Write-Host "Built $archive"
