$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\pip install -r requirements.txt -q
Write-Host "Starting web UI at http://127.0.0.1:5000"
.\.venv\Scripts\python main.py --mode web --host 127.0.0.1 --port 5000