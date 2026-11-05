$ErrorActionPreference = 'Stop'

$WorkspaceRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $WorkspaceRoot

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Silicon Studio IDE V3.0 - 1-Click Bootstrap" -ForegroundColor Cyan
Write-Host "  Workspace: $WorkspaceRoot" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Create or reuse .venv
$VenvPython = Join-Path $WorkspaceRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    Write-Host "[1/4] Creating Python virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[1/4] Found existing virtual environment (.venv)" -ForegroundColor Green
}

# 2. Install required packages
Write-Host ""
Write-Host "[2/4] Installing FastMCP, FastAPI, Uvicorn, NetworkX, and Watchdog..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install fastmcp fastapi uvicorn websockets watchdog networkx --quiet
Write-Host "  [OK] Python dependencies installed." -ForegroundColor Green

# 3. Verify OSS CAD Suite
$OssBin = 'C:\oss-cad-suite\bin'
Write-Host ""
Write-Host "[3/4] Verifying YosysHQ OSS CAD Suite binaries..." -ForegroundColor Yellow
if (Test-Path $OssBin) {
    Write-Host "  [OK] Found OSS CAD Suite at $OssBin" -ForegroundColor Green
} else {
    Write-Host "  [WARN] C:\oss-cad-suite\bin not found; using system PATH or fallback schemas." -ForegroundColor Yellow
}

# 4. Build all Tool & Canary-Validated Knowledge Base Schemas
Write-Host ""
Write-Host "[4/4] Building Tool Schemas & Running 3-Tier Knowledge Base Canary Gate..." -ForegroundColor Yellow
$env:PYTHONPATH = $WorkspaceRoot
$env:PYTHONUTF8 = '1'
& $VenvPython -m schema_factory.build_all_schemas --all

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Bootstrap Complete! Start the IDE anytime with:" -ForegroundColor Green
Write-Host "    powershell -ExecutionPolicy Bypass -File .\scripts\start_studio.ps1" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
