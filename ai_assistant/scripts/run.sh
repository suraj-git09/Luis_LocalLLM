#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "Created .env from .env.example — update it before production use."
  else
    echo "Warning: .env file not found." >&2
  fi
fi

if [[ ! -d .venv ]]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "Running tests..."
python -m pytest tests/ -q

echo "Starting AI Assistant (text mode)..."
exec python main.py --mode text "$@"