# Start Churn Insights as one server: builds the frontend when needed, then serves UI + API.
#   .\start.ps1               -> http://127.0.0.1:8000
#   .\start.ps1 -Port 9000
param([int]$Port = 8000, [switch]$Rebuild)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$node = Join-Path $env:LOCALAPPDATA "Programs\nodejs"
if (Test-Path $node) { $env:Path = "$node;$env:Path" }

if ($Rebuild -or -not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Push-Location (Join-Path $root "frontend")
    try {
        if (-not (Test-Path "node_modules")) { npm install --no-fund --no-audit }
        npm run build
    } finally { Pop-Location }
}

$python = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Backend venv not found. See README.md > Setup." }
Push-Location (Join-Path $root "backend")
try {
    Write-Host "Churn Insights on http://127.0.0.1:$Port  (API docs: /api/docs)"
    & $python -m uvicorn app.main:app --host 127.0.0.1 --port $Port
} finally { Pop-Location }
