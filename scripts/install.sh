#!/usr/bin/env bash
# AI Content Discovery Assistant – Ubuntu 24.04 installer
set -euo pipefail

APP_NAME="ai-content-discovery"
APP_USER="aicontent"
APP_DIR="/opt/${APP_NAME}"
SERVICE_NAME="${APP_NAME}"
PYTHON_MIN="3.12"

echo "=============================================="
echo "  AI Content Discovery Assistant – Installer"
echo "  Target: Ubuntu 24.04 LTS"
echo "=============================================="
echo

# Must run as root
if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root (use sudo)."
  exit 1
fi

# ------------------------------------------------------------------
# System packages
# ------------------------------------------------------------------
echo "[1/8] Updating package lists…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

echo "[2/8] Installing system dependencies…"
apt-get install -y -qq \
  python3 \
  python3-venv \
  python3-dev \
  python3-pip \
  git \
  curl \
  build-essential \
  libffi-dev \
  libssl-dev \
  sqlite3 \
  ca-certificates

# Optional but useful
apt-get install -y -qq ffmpeg || true

# ------------------------------------------------------------------
# Application user
# ------------------------------------------------------------------
echo "[3/8] Creating application user (${APP_USER})…"
if ! id -u "${APP_USER}" &>/dev/null; then
  useradd --system --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

# ------------------------------------------------------------------
# Application directory
# ------------------------------------------------------------------
echo "[4/8] Setting up application directory…"
mkdir -p "${APP_DIR}"
# Copy current project files (assumes the script is run from the repo root
# or that the repo has already been cloned into APP_DIR)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ "${REPO_ROOT}" != "${APP_DIR}" ]]; then
  rsync -a --delete \
    --exclude '.venv' \
    --exclude 'logs' \
    --exclude 'data' \
    --exclude '.env' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    "${REPO_ROOT}/" "${APP_DIR}/"
fi

mkdir -p "${APP_DIR}/logs" "${APP_DIR}/data"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# ------------------------------------------------------------------
# Python virtual environment
# ------------------------------------------------------------------
echo "[5/8] Creating Python virtual environment…"
sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip wheel setuptools -q
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt" -q

# ------------------------------------------------------------------
# Environment file
# ------------------------------------------------------------------
echo "[6/8] Preparing environment file…"
if [[ ! -f "${APP_DIR}/.env" ]]; then
  cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
  chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env"
  chmod 600 "${APP_DIR}/.env"
  echo "  → Created ${APP_DIR}/.env from template."
  echo "  → IMPORTANT: Edit this file and fill in your real credentials."
else
  echo "  → Existing .env found, leaving it untouched."
fi

# ------------------------------------------------------------------
# systemd service
# ------------------------------------------------------------------
echo "[7/8] Installing systemd service…"
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << SYSTEMD
[Unit]
Description=AI Content Discovery Assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONPATH=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/run.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${APP_NAME}

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${APP_DIR}/logs ${APP_DIR}/data

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"

# ------------------------------------------------------------------
# Done
# ------------------------------------------------------------------
echo "[8/8] Installation complete."
echo
echo "Next steps:"
echo "  1. Edit the configuration:"
echo "       sudo nano ${APP_DIR}/.env"
echo "  2. Start the service:"
echo "       sudo systemctl start ${SERVICE_NAME}"
echo "  3. Check status:"
echo "       sudo systemctl status ${SERVICE_NAME}"
echo "  4. Follow logs:"
echo "       sudo journalctl -u ${SERVICE_NAME} -f"
echo
echo "The bot will only accept messages from users listed in TELEGRAM_ALLOWED_USER_IDS."
