from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


class LogsPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        clear_button = QPushButton("清空界面日志")
        clear_button.clicked.connect(self.clear)
        copy_button = QPushButton("复制日志")
        copy_button.clicked.connect(self.copy)
        load_button = QPushButton("读取最近日志文件")
        load_button.clicked.connect(self.load_recent_log)
        buttons.addWidget(clear_button)
        buttons.addWidget(copy_button)
        buttons.addWidget(load_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        self.context.log_message.connect(self.append)

    def append(self, message: str) -> None:
        self.text.append(message)

    def clear(self) -> None:
        self.text.clear()

    def copy(self) -> None:
        QGuiApplication.clipboard().setText(self.text.toPlainText())
        self.append("日志已复制到剪贴板。")

    def load_recent_log(self) -> None:
        logs_dir = self.context.paths.gateway_dir / "logs"
        if not logs_dir.exists():
            self.append("项目下未发现 logs 目录。")
            return
        files = sorted((p for p in logs_dir.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            self.append("logs 目录中没有日志文件。")
            return
        latest: Path = files[0]
        self.append(f"读取最近日志：{latest}")
        self.append(latest.read_text(encoding="utf-8", errors="replace")[-8000:])
