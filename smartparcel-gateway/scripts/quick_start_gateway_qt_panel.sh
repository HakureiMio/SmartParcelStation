#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${GATEWAY_DIR}"

if [ ! -x ".venv/bin/python" ]; then
  echo "未找到可用的 .venv/bin/python。"
  echo "请先执行：bash scripts/install_qt_panel_deps.sh"
  exit 1
fi

# shellcheck source=/dev/null
source ".venv/bin/activate"

MODE="${1:-${GATEWAY_MODE:-local-api}}"
HOST="${GATEWAY_HOST:-127.0.0.1}"
PORT="${GATEWAY_PORT:-19000}"
LOG_DIR="${GATEWAY_LOG_DIR:-${GATEWAY_DIR}/logs}"
mkdir -p "${LOG_DIR}"

case "${MODE}" in
  local-api)
    GATEWAY_CMD=(python -m gateway.main local-api --host "${HOST}" --port "${PORT}")
    GATEWAY_LOG="${LOG_DIR}/quick-start-local-api.log"
    ;;
  run)
    GATEWAY_CMD=(python -m gateway.main run)
    GATEWAY_LOG="${LOG_DIR}/quick-start-gateway-run.log"
    ;;
  *)
    echo "用法：bash scripts/quick_start_gateway_qt_panel.sh [local-api|run]"
    echo "默认：local-api"
    exit 2
    ;;
esac

cleanup() {
  if [ -n "${GATEWAY_PID:-}" ] && kill -0 "${GATEWAY_PID}" 2>/dev/null; then
    echo "正在停止 gateway 进程：${GATEWAY_PID}"
    kill "${GATEWAY_PID}" 2>/dev/null || true
    wait "${GATEWAY_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "已进入虚拟环境：${VIRTUAL_ENV}"
echo "启动 gateway (${MODE})，日志：${GATEWAY_LOG}"
"${GATEWAY_CMD[@]}" >"${GATEWAY_LOG}" 2>&1 &
GATEWAY_PID=$!

sleep 1
if ! kill -0 "${GATEWAY_PID}" 2>/dev/null; then
  echo "gateway 启动失败，最近日志："
  tail -n 80 "${GATEWAY_LOG}" || true
  exit 1
fi

echo "gateway 进程已启动：${GATEWAY_PID}"
echo "启动 Qt 面板..."
python tools/gateway_qt_panel/main.py
