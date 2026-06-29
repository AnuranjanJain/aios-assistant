$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

python -m pip install -r requirements-desktop.txt
python -m PyInstaller --clean --noconfirm desktop_app.spec

$output = Join-Path $repo "release\windows"
New-Item -ItemType Directory -Force -Path $output | Out-Null
Copy-Item "dist\AiOS-Assistant.exe" $output -Force
Copy-Item "scripts\install-desktop.ps1" $output -Force

$archive = Join-Path $repo "release\AiOS-Assistant-windows-x64.zip"
if (Test-Path $archive) {
    Remove-Item -LiteralPath $archive -Force
}
Compress-Archive -Path "$output\AiOS-Assistant.exe", "$output\install-desktop.ps1" -DestinationPath $archive

Write-Host "Built $archive"
