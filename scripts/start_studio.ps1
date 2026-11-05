$ErrorActionPreference = 'Stop'

$WorkspaceRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $WorkspaceRoot

$VenvPython = Join-Path $WorkspaceRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    $VenvPython = 'python'
}

$env:PYTHONPATH = $WorkspaceRoot
$env:PYTHONUTF8 = '1'

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Launching Silicon Studio IDE V3.0 on http://127.0.0.1:8080" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

Start-Process 'http://127.0.0.1:8080'
& $VenvPython "$WorkspaceRoot\backend\server\studio_server.py"
