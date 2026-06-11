# Production run script (Windows)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example — update it before production use."
    } else {
        Write-Warning ".env file not found."
    }
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

Write-Host "Installing dependencies..."
.\.venv\Scripts\python -m pip install --upgrade pip -q
.\.venv\Scripts\pip install -r requirements.txt -q

Write-Host "Running tests..."
.\.venv\Scripts\python -m pytest tests/ -q
if ($LASTEXITCODE -ne 0) {
    throw "Tests failed. Aborting startup."
}

Write-Host "Starting AI Assistant (text mode)..."
.\.venv\Scripts\python main.py --mode text @args