#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ── Ensure uv is available ─────────────────────────────────────────────────
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  ERROR: 'uv' is not installed." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Install it with:"
    Write-Host "    powershell -c `"irm https://astral.sh/uv/install.ps1 | iex`""
    Write-Host "  or:"
    Write-Host "    pip install uv"
    Write-Host ""
    exit 1
}

Write-Host "==> Syncing dependencies..."
uv sync --quiet

Write-Host "==> Running migrations..."
uv run python manage.py migrate --run-syncdb

if (-not (Test-Path ".seeded")) {
    Write-Host "==> Seeding test data (first run)..."
    uv run python manage.py seed
    New-Item -ItemType File -Path ".seeded" -Force | Out-Null
}

# ── Free port 8000 if already in use ──────────────────────────────────────
$portPids = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess
if ($portPids) {
    Write-Host "==> Stopping existing process on port 8000..."
    $portPids | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "==> StudentGig is running at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host ""
Write-Host "    Home    http://127.0.0.1:8000/"
Write-Host "    Login   http://127.0.0.1:8000/accounts/login/"
Write-Host "    Admin   http://127.0.0.1:8000/admin/  (admin / admin)"
Write-Host ""
Write-Host "    Test accounts:"
Write-Host "      student1 / pass1234  (KYC verified)"
Write-Host "      client1  / pass1234  (KYC verified)"
Write-Host "      student2 / pass1234  (KYC pending)"
Write-Host ""

uv run python manage.py runserver 8000
