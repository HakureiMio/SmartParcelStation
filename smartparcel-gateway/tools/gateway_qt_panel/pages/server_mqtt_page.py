from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget

from api_client import ApiClient, server_health
from env_editor import load_env


class ServerMqttPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.server_url = QLabel()
        self.mqtt_host = QLabel()
        self.mqtt_port = QLabel()
        self.mqtt_username = QLabel()
        self.mqtt_password = QLineEdit()
        self.mqtt_password.setEchoMode(QLineEdit.Password)
        self.mqtt_password.setReadOnly(True)
        for label, widget in [
            ("SERVER_BASE_URL：", self.server_url),
            ("MQTT_HOST：", self.mqtt_host),
            ("MQTT_PORT：", self.mqtt_port),
            ("MQTT_USERNAME：", self.mqtt_username),
            ("MQTT_PASSWORD：", self.mqtt_password),
        ]:
            form.addRow(label, widget)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        server_button = QPushButton("测试 Server Health")
        server_button.clicked.connect(self.test_server)
        local_button = QPushButton("测试 Local Health")
        local_button.clicked.connect(self.test_local)
        copy_button = QPushButton("复制 Topic")
        copy_button.clicked.connect(self.copy_topics)
        buttons.addWidget(server_button)
        buttons.addWidget(local_button)
        buttons.addWidget(copy_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.topics = QTextEdit()
        self.topics.setReadOnly(True)
        layout.addWidget(self.topics)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh()

    def refresh(self) -> None:
        env = load_env(self.context.paths.env_path)
        gateway_code = env.get("GATEWAY_CODE", "{gateway_code}")
        self.server_url.setText(env.get("SERVER_BASE_URL", ""))
        self.mqtt_host.setText(env.get("MQTT_HOST", ""))
        self.mqtt_port.setText(env.get("MQTT_PORT", ""))
        self.mqtt_username.setText(env.get("MQTT_USERNAME", ""))
        self.mqtt_password.setText(env.get("MQTT_PASSWORD", ""))
        self.topics.setPlainText(
            "\n".join(
                [
                    f"server/{gateway_code}/commands",
                    f"gateway/{gateway_code}/status",
                    f"gateway/{gateway_code}/events",
                    "",
                    "TODO：后续可以扩展 MQTT 实时订阅观察；本页当前只展示 topic 模板和基础连通性检查。",
                ]
            )
        )

    def test_server(self) -> None:
        try:
            self._append(f"Server health 正常：{server_health(self.server_url.text())}")
        except Exception as exc:
            self._append(f"Server health 失败：{exc}")

    def test_local(self) -> None:
        try:
            self._append(f"Local API 正常：{ApiClient().health()}")
        except Exception as exc:
            self._append(f"Local API 失败：{exc}")

    def copy_topics(self) -> None:
        QGuiApplication.clipboard().setText(self.topics.toPlainText())
        self._append("Topic 模板已复制到剪贴板。")

    def _append(self, text: str) -> None:
        self.output.append(text)
        self.context.log(text)
