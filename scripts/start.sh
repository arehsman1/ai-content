#!/usr/bin/env bash
# Convenience script to start the application in the foreground (development)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

if [[ ! -d ".venv" ]]; then
  echo "Virtual environment not found. Creating one…"
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip wheel setuptools -q
  .venv/bin/pip install -r requirements.txt -q
fi

if [[ ! -f ".env" ]]; then
  echo "No .env file found. Copying from .env.example…"
  cp .env.example .env
  echo "Please edit .env and add your credentials before starting."
  exit 1
fi

export PYTHONPATH="${REPO_ROOT}"
exec .venv/bin/python run.py
