#!/usr/bin/env bash
# AI Content Discovery Assistant – update script
set -euo pipefail

APP_NAME="ai-content-discovery"
APP_USER="aicontent"
APP_DIR="/opt/${APP_NAME}"
SERVICE_NAME="${APP_NAME}"

if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (use sudo)."
  exit 1
fi

if [[ ! -d "${APP_DIR}" ]]; then
  echo "Application directory ${APP_DIR} not found. Run install.sh first."
  exit 1
fi

echo "Updating ${APP_NAME}…"

# Stop the service
systemctl stop "${SERVICE_NAME}" || true

# Pull latest code if this is a git checkout
if [[ -d "${APP_DIR}/.git" ]]; then
  echo "Pulling latest changes from git…"
  sudo -u "${APP_USER}" git -C "${APP_DIR}" pull --ff-only
else
  # Fallback: rsync from the directory where this script lives
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
  if [[ "${REPO_ROOT}" != "${APP_DIR}" ]]; then
    echo "Syncing files from ${REPO_ROOT}…"
    rsync -a \
      --exclude '.venv' \
      --exclude 'logs' \
      --exclude 'data' \
      --exclude '.env' \
      --exclude '__pycache__' \
      --exclude '*.pyc' \
      --exclude '.git' \
      "${REPO_ROOT}/" "${APP_DIR}/"
  fi
fi

# Update Python dependencies
echo "Updating Python dependencies…"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip -q
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# Restart
systemctl daemon-reload
systemctl start "${SERVICE_NAME}"

echo "Update complete. Service status:"
systemctl --no-pager status "${SERVICE_NAME}" || true
