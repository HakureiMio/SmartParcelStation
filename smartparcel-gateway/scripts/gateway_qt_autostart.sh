#!/usr/bin/env bash
# Usage: bash scripts/gateway_qt_autostart.sh enable|disable|status
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATEWAY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_PATH="${GATEWAY_DIR}/.venv/bin/python"
SERVICE_NAME="smartparcel-gateway.service"
USER_SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${USER_SERVICE_DIR}/${SERVICE_NAME}"
AUTOSTART_DIR="${HOME}/.config/autostart"
DESKTOP_FILE="${AUTOSTART_DIR}/smartparcel-gateway-qt.desktop"
QT_LAUNCHER="${SCRIPT_DIR}/autostart_qt_panel.sh"
ACTION="${1:-status}"

require_runtime() {
  if [ ! -x "${PYTHON_PATH}" ]; then
    echo "未找到 ${PYTHON_PATH}。请先执行 bash scripts/install_qt_panel_deps.sh" >&2
    exit 1
  fi
  if ! command -v systemctl >/dev/null 2>&1; then
    echo "未检测到 systemctl；该开关适用于带 systemd 的 Linux 桌面环境。" >&2
    exit 1
  fi
}

is_enabled() {
  [ -f "${SERVICE_FILE}" ] && [ -f "${DESKTOP_FILE}" ] && \
    systemctl --user is-enabled "${SERVICE_NAME}" >/dev/null 2>&1
}

enable_autostart() {
  require_runtime
  mkdir -p "${USER_SERVICE_DIR}" "${AUTOSTART_DIR}"
  cat >"${SERVICE_FILE}" <<EOF
[Unit]
Description=SmartParcel Gateway User Service
After=network-online.target bluetooth.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${GATEWAY_DIR}
Environment=PYTHONUNBUFFERED=1
ExecStart=${PYTHON_PATH} -m gateway.main run
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
  cat >"${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=SmartParcel Gateway Qt Panel
Comment=Open the SmartParcel Gateway control panel after desktop login
Exec=/bin/bash ${QT_LAUNCHER}
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
  chmod +x "${QT_LAUNCHER}"
  systemctl --user daemon-reload
  systemctl --user enable --now "${SERVICE_NAME}"
  echo "已启用：Gateway 用户服务开机启动，Qt 面板在桌面登录后打开。"
}

disable_autostart() {
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user disable --now "${SERVICE_NAME}" >/dev/null 2>&1 || true
  fi
  rm -f "${SERVICE_FILE}" "${DESKTOP_FILE}"
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
  fi
  echo "已关闭 Gateway 与 Qt 面板的自动启动。"
}

show_status() {
  if is_enabled; then
    echo "enabled"
    systemctl --user --no-pager status "${SERVICE_NAME}" || true
    exit 0
  fi
  echo "disabled"
  exit 1
}

case "${ACTION}" in
  enable) enable_autostart ;;
  disable) disable_autostart ;;
  status) show_status ;;
  *) echo "用法：bash scripts/gateway_qt_autostart.sh enable|disable|status" >&2; exit 2 ;;
esac
