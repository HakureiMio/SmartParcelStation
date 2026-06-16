from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from api_client import ApiClient
from app_config import LOCAL_API_BASE_URL


class LocalApiPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        self.status = QLabel("Local API 状态：待测试")
        layout.addWidget(QLabel(f"默认地址：{LOCAL_API_BASE_URL}"))
        layout.addWidget(self.status)
        layout.addWidget(QLabel("启动提示命令：python -m gateway.main local-api --host 127.0.0.1 --port 19000"))
        buttons = QHBoxLayout()
        health_button = QPushButton("测试 /local/health")
        health_button.clicked.connect(self.test_health)
        tags_button = QPushButton("测试 /local/tags")
        tags_button.clicked.connect(self.test_tags)
        buttons.addWidget(health_button)
        buttons.addWidget(tags_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def test_health(self) -> None:
        try:
            data = ApiClient().health()
            self.status.setText("Local API 状态：在线")
            self._append(f"/local/health 正常：{data}")
        except Exception as exc:
            self.status.setText("Local API 状态：离线")
            self._append(f"/local/health 失败：{exc}")

    def test_tags(self) -> None:
        try:
            data = ApiClient().list_tags()
            self.status.setText("Local API 状态：在线")
            self._append(f"/local/tags 正常：{data}")
        except Exception as exc:
            self.status.setText("Local API 状态：离线")
            self._append(f"/local/tags 失败：{exc}")

    def _append(self, text: str) -> None:
        self.output.append(text)
        self.context.log(text)
