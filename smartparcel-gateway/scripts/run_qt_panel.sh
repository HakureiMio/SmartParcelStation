#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${GATEWAY_DIR}"

if [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="${PYTHON:-python3}"
fi

exec "${PYTHON_BIN}" tools/gateway_qt_panel/main.py
