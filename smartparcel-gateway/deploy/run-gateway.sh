#!/usr/bin/env bash
# SmartParcel Gateway — Runtime Launcher
#
# Usage:
#   chmod +x run-gateway.sh
#   ./run-gateway.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate venv if it exists
if [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

echo "Starting SmartParcel Gateway..."
exec python -m gateway.main run
