<#
.SYNOPSIS
    One-time local development setup: Python venv + backend deps, npm workspaces, .env.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating .venv" -ForegroundColor Cyan
    python -m venv .venv
}
Write-Host "==> Installing backend dependencies" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -e .
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

Write-Host "==> Installing npm workspaces" -ForegroundColor Cyan
npm ci
if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> Created .env from .env.example" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Green
Write-Host "  fill the fotomind_dev password in .env (DB on the Pi), then:"
Write-Host "  .\.venv\Scripts\fotomind-api"
Write-Host "  npm run dev:web"
Write-Host "  .\scripts\pi-check.ps1   (Docker checks run on the Pi)"
