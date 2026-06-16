from __future__ import annotations

import shutil
import sys

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app_config import FIRST_BOOT_KEYS
from command_runner import CommandRunner
from env_editor import load_env, save_env


class FirstBootPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.inputs: dict[str, QLineEdit] = {}
        layout = QVBoxLayout(self)
        self.status = QLabel()
        layout.addWidget(self.status)

        form = QFormLayout()
        for key in FIRST_BOOT_KEYS:
            field = QLineEdit()
            if key == "MQTT_PASSWORD":
                field.setEchoMode(QLineEdit.Password)
            self.inputs[key] = field
            form.addRow(f"{key}：", field)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        for text, slot in [
            ("从 .env.example 创建", self.create_from_example),
            ("保存配置", self.save),
            ("执行 init-db", self.init_db),
            ("执行 health", self.health),
        ]:
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        layout.addWidget(QLabel("Bootstrap 激活"))
        activate_form = QFormLayout()
        self.activate_gateway_code = QLineEdit()
        self.activate_station_id = QLineEdit()
        self.activate_token = QLineEdit()
        self.activate_token.setEchoMode(QLineEdit.Password)
        self.activate_server_url = QLineEdit()
        activate_form.addRow("gateway_code：", self.activate_gateway_code)
        activate_form.addRow("station_id：", self.activate_station_id)
        activate_form.addRow("registration_token：", self.activate_token)
        activate_form.addRow("server_base_url：", self.activate_server_url)
        layout.addLayout(activate_form)
        activate_button = QPushButton("激活网关")
        activate_button.clicked.connect(self.bootstrap_activate)
        layout.addWidget(activate_button)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.runner = CommandRunner(self.context.paths.gateway_dir)
        self.runner.output.connect(self._append)
        self.runner.finished.connect(lambda _code: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        exists = self.context.paths.env_path.exists()
        self.status.setText(f".env 状态：{'存在' if exists else '不存在'}")
        env = load_env(self.context.paths.env_path)
        for key, field in self.inputs.items():
            field.setText(env.get(key, ""))
        self.activate_gateway_code.setText(env.get("GATEWAY_CODE", "GW001"))
        self.activate_station_id.setText(env.get("STATION_ID", "1"))
        self.activate_server_url.setText(env.get("SERVER_BASE_URL", "http://127.0.0.1:18000"))

    def create_from_example(self) -> None:
        if self.context.paths.env_path.exists():
            QMessageBox.information(self, "提示", ".env 已存在，不需要创建。")
            return
        shutil.copy2(self.context.paths.env_example_path, self.context.paths.env_path)
        self._append("已从 .env.example 创建 .env")
        self.refresh()

    def save(self) -> None:
        updates = {key: field.text().strip() for key, field in self.inputs.items()}
        backup = save_env(self.context.paths.env_path, updates, FIRST_BOOT_KEYS)
        self._append(f"配置已保存，备份文件：{backup}")
        QMessageBox.information(self, "已保存", "配置已保存。重启 gateway 后完全生效。")

    def init_db(self) -> None:
        self.runner.run([sys.executable, "-m", "gateway.main", "init-db"])

    def health(self) -> None:
        self.runner.run([sys.executable, "-m", "gateway.main", "health"])

    def bootstrap_activate(self) -> None:
        if not self.activate_token.text().strip():
            QMessageBox.warning(self, "缺少信息", "请输入 registration_token。")
            return
        if QMessageBox.question(self, "确认激活", "激活会向 .env 写入网关配置并备份原文件，是否继续？") != QMessageBox.Yes:
            return
        self.runner.run(
            [
                sys.executable,
                "-m",
                "gateway.main",
                "bootstrap-activate",
                "--gateway-code",
                self.activate_gateway_code.text().strip(),
                "--station-id",
                self.activate_station_id.text().strip(),
                "--registration-token",
                self.activate_token.text().strip(),
                "--server-base-url",
                self.activate_server_url.text().strip(),
            ]
        )

    def _append(self, text: str) -> None:
        self.output.append(text)
        self.context.log(text)
