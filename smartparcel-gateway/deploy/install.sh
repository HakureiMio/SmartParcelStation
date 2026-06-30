#!/usr/bin/env bash
# SmartParcel Gateway — Installation Script
# Target: Ubuntu / Debian / Raspberry Pi OS
#
# Usage:
#   chmod +x install.sh
#   ./install.sh
#
# What this does:
# 1. Creates Python venv
# 2. Installs Python dependencies
# 3. Initializes SQLite database
# 4. Copies .env.example → .env if .env does not exist
# 5. Prompts user to configure required settings

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== SmartParcel Gateway Installer ==="
echo "Project directory: $PROJECT_DIR"
echo ""

# --- Python venv ---
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "[1/5] Creating Python virtual environment..."
    python3 -m venv "$PROJECT_DIR/.venv"
else
    echo "[1/5] Virtual environment already exists, skipping."
fi

# Activate
source "$PROJECT_DIR/.venv/bin/activate"

# --- Dependencies ---
echo "[2/5] Installing Python dependencies..."
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

# --- .env configuration ---
echo "[3/5] Configuring environment..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "  Created .env from .env.example"
    echo ""
    echo "  >>> IMPORTANT: Edit $PROJECT_DIR/.env and set at minimum:"
    echo "      GATEWAY_DEVICE_ID    (e.g. GWDEV-0001)"
    echo "      GATEWAY_SERIAL       (e.g. SPS-GW-0001)"
    echo "      WIFI_AP_PASSWORD     (min 8 chars for WPA2)"
    echo "      SQLITE_PATH          (default: ./data/gateway.db)"
    echo ""
    echo "  Do NOT set GATEWAY_SECRET — it will be issued by the server during binding."
else
    echo "  .env already exists, skipping."
fi

# --- Database ---
echo "[4/5] Initializing SQLite database..."
cd "$PROJECT_DIR"
python -m gateway.main init-db
echo "  Database initialized."

# --- Verify ---
echo "[5/5] Verifying installation..."
python -m gateway.main status || echo "  (status shows UNBOUND — this is normal before binding)"

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and set GATEWAY_DEVICE_ID, GATEWAY_SERIAL, WIFI_AP_PASSWORD"
echo "  2. Start provisioning mode:  python -m gateway.main provisioning"
echo "  3. Or auto-start:             python -m gateway.main run"
echo ""
echo "For systemd auto-start, see deploy/smartparcel-gateway.service.example"
