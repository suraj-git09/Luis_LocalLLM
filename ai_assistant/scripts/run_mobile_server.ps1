# Start PC as mobile API server (LAN accessible)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\pip install -r requirements.txt -q
Write-Host "Starting Mobile API Server on all network interfaces (port 5000)..."
.\.venv\Scripts\python mobile_api_server.py --host 0.0.0.0 --port 5000