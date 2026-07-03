# Zip the built Goyquest folder for GitHub Releases (or manual distribution).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$source = Join-Path $PSScriptRoot "dist\Goyquest"
$zip = Join-Path $PSScriptRoot "dist\Goyquest-windows.zip"

if (-not (Test-Path (Join-Path $source "Goyquest.exe"))) {
    throw "Build first: .\build.ps1"
}

if (Test-Path $zip) {
    Remove-Item $zip -Force
}

Compress-Archive -Path $source -DestinationPath $zip
Write-Host "Created: $zip"
Write-Host "Upload this file to GitHub Releases."