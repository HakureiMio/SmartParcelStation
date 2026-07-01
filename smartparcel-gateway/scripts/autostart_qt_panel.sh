#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_PATH="${GATEWAY_DIR}/.venv/bin/python"

if [ ! -x "${PYTHON_PATH}" ]; then
  echo "未找到 ${PYTHON_PATH}，请先安装 Gateway Qt 依赖。" >&2
  exit 1
fi

# 给桌面会话和后台 Gateway 留出初始化时间。
sleep "${SPS_QT_AUTOSTART_DELAY_SECONDS:-3}"
cd "${GATEWAY_DIR}"
exec "${PYTHON_PATH}" tools/gateway_qt_panel/main.py
