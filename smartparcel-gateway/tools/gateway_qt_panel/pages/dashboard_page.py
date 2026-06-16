from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from api_client import ApiClient, server_health
from app_config import LOCAL_API_BASE_URL, resolve_gateway_path, system_summary
from env_editor import load_env


class DashboardPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.values: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("网关本地状态总览"))

        form = QFormLayout()
        for label in [
            "GATEWAY_CODE",
            "STATION_ID",
            "SERVER_BASE_URL",
            "SQLITE_PATH",
            "BLE_BACKEND",
            "MQTT_HOST",
            "MQTT_PORT",
            "Local API",
            ".env",
            "SQLite 数据库",
            "Local API 状态",
            "Server Health",
            "MQTT 配置",
            "系统平台",
            "工作目录",
            "Python 版本",
        ]:
            value = QLabel("-")
            value.setTextInteractionFlags(value.textInteractionFlags() | Qt.TextSelectableByMouse)
            self.values[label] = value
            form.addRow(f"{label}：", value)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        for text, slot in [
            ("刷新状态", self.refresh),
            ("打开 .env 目录", self.open_env_dir),
            ("测试 Local API", self.test_local_api),
            ("测试 Server Health", self.test_server),
            ("测试 MQTT 配置", self.test_mqtt_config),
        ]:
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh()

    def refresh(self) -> None:
        env = load_env(self.context.paths.env_path)
        db_path = resolve_gateway_path(self.context.paths.gateway_dir, env.get("SQLITE_PATH"))
        mapping = {
            "GATEWAY_CODE": env.get("GATEWAY_CODE", "-"),
            "STATION_ID": env.get("STATION_ID", "-"),
            "SERVER_BASE_URL": env.get("SERVER_BASE_URL", "-"),
            "SQLITE_PATH": str(db_path),
            "BLE_BACKEND": env.get("BLE_BACKEND", "-"),
            "MQTT_HOST": env.get("MQTT_HOST", "-"),
            "MQTT_PORT": env.get("MQTT_PORT", "-"),
            "Local API": LOCAL_API_BASE_URL,
            ".env": "存在" if self.context.paths.env_path.exists() else "不存在",
            "SQLite 数据库": "存在" if db_path.exists() else "不存在",
            "Local API 状态": "待测试",
            "Server Health": "待测试",
            "MQTT 配置": "完整" if self._mqtt_complete(env) else "不完整",
        }
        mapping.update(system_summary(self.context.paths.gateway_dir))
        for key, value in mapping.items():
            self.values[key].setText(str(value))

    def open_env_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.env_path.parent)))

    def test_local_api(self) -> None:
        try:
            data = ApiClient().health()
            self.values["Local API 状态"].setText("可访问")
            self._append(f"Local API 正常：{data}")
        except Exception as exc:
            self.values["Local API 状态"].setText("不可访问")
            self._append(f"Local API 失败：{exc}")

    def test_server(self) -> None:
        env = load_env(self.context.paths.env_path)
        try:
            data = server_health(env.get("SERVER_BASE_URL", ""))
            self.values["Server Health"].setText("可访问")
            self._append(f"Server health 正常：{data}")
        except Exception as exc:
            self.values["Server Health"].setText("不可访问")
            self._append(f"Server health 失败：{exc}")

    def test_mqtt_config(self) -> None:
        env = load_env(self.context.paths.env_path)
        ok = self._mqtt_complete(env)
        self.values["MQTT 配置"].setText("完整" if ok else "不完整")
        self._append("MQTT 基础配置完整。" if ok else "MQTT_HOST 或 MQTT_PORT 缺失。")

    def _mqtt_complete(self, env: dict[str, str]) -> bool:
        return bool(env.get("MQTT_HOST") and env.get("MQTT_PORT"))

    def _append(self, text: str) -> None:
        self.output.append(text)
        self.context.log(text)
