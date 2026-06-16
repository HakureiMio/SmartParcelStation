from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget

from app_config import CONFIG_ALLOWED_KEYS, bool_to_env, env_to_bool
from env_editor import load_env, save_env


class ConfigPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.widgets = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("白名单配置表单。未知字段会保留，不会删除。"))
        form = QFormLayout()
        for key in CONFIG_ALLOWED_KEYS:
            widget = self._make_widget(key)
            self.widgets[key] = widget
            form.addRow(f"{key}：", widget)
        layout.addLayout(form)
        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self.save)
        layout.addWidget(save_button)
        layout.addStretch()
        self.refresh()

    def _make_widget(self, key: str):
        if key == "BLE_BACKEND":
            widget = QComboBox()
            widget.addItems(["mock", "real"])
            return widget
        if key == "LOG_LEVEL":
            widget = QComboBox()
            widget.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
            return widget
        if key in {"MOCK_NFC_ENABLED", "MOCK_BLE_ENABLED"}:
            return QCheckBox("启用")
        if key.endswith("_INTERVAL_SECONDS") or key == "MQTT_PORT":
            widget = QSpinBox()
            widget.setRange(0, 86400)
            return widget
        widget = QLineEdit()
        if key == "MQTT_PASSWORD":
            widget.setEchoMode(QLineEdit.Password)
        return widget

    def refresh(self) -> None:
        env = load_env(self.context.paths.env_path)
        for key, widget in self.widgets.items():
            value = env.get(key, "")
            if isinstance(widget, QComboBox):
                index = widget.findText(value)
                widget.setCurrentIndex(index if index >= 0 else 0)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(env_to_bool(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value or 0))
            else:
                widget.setText(value)

    def save(self) -> None:
        updates = {}
        for key, widget in self.widgets.items():
            if isinstance(widget, QComboBox):
                updates[key] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                updates[key] = bool_to_env(widget.isChecked())
            elif isinstance(widget, QSpinBox):
                updates[key] = str(widget.value())
            else:
                updates[key] = widget.text().strip()
        backup = save_env(self.context.paths.env_path, updates, CONFIG_ALLOWED_KEYS)
        self.context.log(f"配置已保存，备份文件：{backup}")
        QMessageBox.information(self, "已保存", f"配置已保存，备份文件：{backup}\n重启 gateway 进程后完全生效。")
