# Build Goyquest.exe (folder distribution — lower AV false positives than onefile).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing build dependencies..."
python -m pip install -r requirements-build.txt

Write-Host "Building Goyquest (onedir, no UPX)..."
python -m PyInstaller --noconfirm --clean goyquest.spec

$out = Join-Path $PSScriptRoot "dist\Goyquest"
if (-not (Test-Path (Join-Path $out "Goyquest.exe"))) {
    throw "Build failed: Goyquest.exe not found in dist\Goyquest"
}

Write-Host ""
Write-Host "Done. Ship this folder (or zip it):"
Write-Host "  $out"
Write-Host ""
Write-Host "Users run: Goyquest.exe"
Write-Host "See BUILD.txt for antivirus notes."
Write-Host "To zip for GitHub Releases: .\package_release.ps1"