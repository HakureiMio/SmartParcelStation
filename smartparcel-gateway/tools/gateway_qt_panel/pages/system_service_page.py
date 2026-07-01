from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from service_manager import (
    check_systemd_service,
    generate_service_template,
    get_systemd_status,
    is_gateway_qt_autostart_enabled,
    set_gateway_qt_autostart,
)


class SystemServicePage(QWidget):
    SERVICE_NAME = "smartparcel-gateway.service"

    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        self.detect_label = QLabel()
        layout.addWidget(self.detect_label)
        self.autostart_checkbox = QCheckBox("桌面登录后自动启动 Gateway 服务并打开 Qt 面板")
        layout.addWidget(self.autostart_checkbox)
        buttons = QHBoxLayout()
        refresh_button = QPushButton("刷新检测")
        refresh_button.clicked.connect(self.refresh)
        copy_button = QPushButton("复制 Service 模板")
        copy_button.clicked.connect(self.copy_template)
        status_button = QPushButton("查看服务状态")
        status_button.clicked.connect(self.show_status)
        apply_autostart_button = QPushButton("应用自动启动开关")
        apply_autostart_button.clicked.connect(self.apply_autostart)
        buttons.addWidget(refresh_button)
        buttons.addWidget(copy_button)
        buttons.addWidget(status_button)
        buttons.addWidget(apply_autostart_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.template = QTextEdit()
        self.template.setReadOnly(True)
        layout.addWidget(self.template)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh()

    def refresh(self) -> None:
        python_path = Path(self.context.paths.gateway_dir / ".venv" / "bin" / "python")
        if not python_path.exists():
            python_path = Path(sys.executable)
        self.template.setPlainText(generate_service_template(self.context.paths.gateway_dir, python_path))
        found = check_systemd_service(self.SERVICE_NAME)
        self.detect_label.setText(f"{self.SERVICE_NAME}：{'已检测到' if found else '未检测到'}")
        self.autostart_checkbox.setChecked(is_gateway_qt_autostart_enabled(self.context.paths.gateway_dir))

    def apply_autostart(self) -> None:
        enabled = self.autostart_checkbox.isChecked()
        result = set_gateway_qt_autostart(self.context.paths.gateway_dir, enabled)
        self._append(result)
        self.refresh()

    def copy_template(self) -> None:
        QGuiApplication.clipboard().setText(self.template.toPlainText())
        self._append("Service 模板已复制到剪贴板。默认不会写入 /etc/systemd/system。")

    def show_status(self) -> None:
        self._append(get_systemd_status("smartparcel-gateway"))

    def _append(self, text: str) -> None:
        self.output.append(text)
        self.context.log(text)
