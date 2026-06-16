from __future__ import annotations

import json

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from api_client import ApiClient
from app_config import CONFIG_ALLOWED_KEYS
from env_editor import load_env, save_env


class ApiWorker(QThread):
    done = Signal(str, dict)
    failed = Signal(str, str)

    def __init__(self, action: str, kwargs: dict):
        super().__init__()
        self.action = action
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            client = ApiClient(timeout=max(8.0, float(self.kwargs.get("timeout_sec", 5)) + 3))
            method = getattr(client, self.action)
            self.done.emit(self.action, method(**self.kwargs))
        except Exception as exc:
            self.failed.emit(self.action, str(exc))


class BlePage(QWidget):
    COLUMNS = ["tag_id", "display_name", "status", "battery_level", "battery_mv", "ble_name", "ble_address", "last_seen_at"]

    def __init__(self, context):
        super().__init__()
        self.context = context
        self.worker: ApiWorker | None = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.backend = QComboBox()
        self.backend.addItems(["mock", "real"])
        self.scan_timeout = QSpinBox()
        self.scan_timeout.setRange(1, 120)
        self.scan_timeout.setValue(5)
        self.tag_id = QLineEdit()
        self.wake_color = QLineEdit("BLUE")
        self.wake_duration = QSpinBox()
        self.wake_duration.setRange(1, 3600)
        self.wake_duration.setValue(30)
        form.addRow("BLE_BACKEND：", self.backend)
        form.addRow("scan timeout：", self.scan_timeout)
        form.addRow("tag_id：", self.tag_id)
        form.addRow("wake 颜色：", self.wake_color)
        form.addRow("wake 时长：", self.wake_duration)
        layout.addLayout(form)
        layout.addWidget(QLabel("mock：无硬件演示；real：使用 bleak 控制真实 BLE 标签。切换后需要重启 local API 才会完全生效。"))

        buttons = QHBoxLayout()
        for text, slot in [
            ("保存 BLE_BACKEND", self.save_backend),
            ("扫描标签", self.scan),
            ("刷新列表", self.list_tags),
            ("连接", self.connect_tag),
            ("唤醒", self.wake_tag),
            ("停止", self.stop_tag),
            ("读取状态", self.read_status),
        ]:
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.cellClicked.connect(self._select_row)
        layout.addWidget(self.table)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh()

    def refresh(self) -> None:
        env = load_env(self.context.paths.env_path)
        index = self.backend.findText(env.get("BLE_BACKEND", "mock"))
        self.backend.setCurrentIndex(index if index >= 0 else 0)

    def save_backend(self) -> None:
        backup = save_env(self.context.paths.env_path, {"BLE_BACKEND": self.backend.currentText()}, CONFIG_ALLOWED_KEYS)
        QMessageBox.information(self, "已保存", f"BLE_BACKEND 已保存，备份文件：{backup}\n重启 local API 后完全生效。")

    def scan(self) -> None:
        self._run("scan_tags", {"timeout_sec": self.scan_timeout.value()})

    def list_tags(self) -> None:
        self._run("list_tags", {})

    def connect_tag(self) -> None:
        self._tag_action("connect_tag")

    def wake_tag(self) -> None:
        tag_id = self.tag_id.text().strip()
        if tag_id:
            self._run("wake_tag", {"tag_id": tag_id, "color": self.wake_color.text().strip() or "BLUE", "duration_sec": self.wake_duration.value()})

    def stop_tag(self) -> None:
        self._tag_action("stop_tag")

    def read_status(self) -> None:
        self._tag_action("read_tag_status")

    def _tag_action(self, action: str) -> None:
        tag_id = self.tag_id.text().strip()
        if not tag_id:
            QMessageBox.warning(self, "缺少 tag_id", "请先输入或从表格选择 tag_id。")
            return
        self._run(action, {"tag_id": tag_id})

    def _run(self, action: str, kwargs: dict) -> None:
        if self.worker and self.worker.isRunning():
            self._append("已有 BLE/API 操作正在执行。")
            return
        self.worker = ApiWorker(action, kwargs)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()
        self._append(f"开始执行：{action}")

    def _done(self, action: str, data: dict) -> None:
        self._append(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
        if action in {"list_tags", "scan_tags", "connect_tag", "wake_tag", "stop_tag", "read_tag_status"}:
            items = data.get("items")
            if items is None and data.get("item"):
                items = [data["item"]]
            if items is not None:
                self._fill_table(items)
            if action != "list_tags":
                QTimer.singleShot(0, self.list_tags)

    def _failed(self, action: str, error: str) -> None:
        self._append(f"{action} 失败：{error}\n请确认 local API 已启动。")

    def _fill_table(self, items: list[dict]) -> None:
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            for col, key in enumerate(self.COLUMNS):
                self.table.setItem(row, col, QTableWidgetItem(str(item.get(key, "") or "")))
        self.table.resizeColumnsToContents()

    def _select_row(self, row: int, _col: int) -> None:
        item = self.table.item(row, 0)
        if item:
            self.tag_id.setText(item.text())

    def _append(self, text: str) -> None:
        self.output.append(text)
        self.context.log(text)
