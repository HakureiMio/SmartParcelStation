from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget

from app_config import DB_TABLE_WHITELIST, resolve_gateway_path
from env_editor import load_env


class DatabasePage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        self.info = QLabel()
        layout.addWidget(self.info)
        row = QHBoxLayout()
        self.table_select = QComboBox()
        self.table_select.addItems(DB_TABLE_WHITELIST)
        refresh_button = QPushButton("刷新表数据")
        refresh_button.clicked.connect(self.refresh_table)
        row.addWidget(QLabel("表："))
        row.addWidget(self.table_select)
        row.addWidget(refresh_button)
        row.addStretch()
        layout.addLayout(row)
        self.table = QTableWidget()
        layout.addWidget(self.table)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        self.refresh_info()

    def _db_path(self):
        env = load_env(self.context.paths.env_path)
        return resolve_gateway_path(self.context.paths.gateway_dir, env.get("SQLITE_PATH"))

    def refresh_info(self) -> None:
        db_path = self._db_path()
        size = db_path.stat().st_size if db_path.exists() else 0
        self.info.setText(f"SQLITE_PATH：{db_path} | 状态：{'存在' if db_path.exists() else '不存在'} | 大小：{size} bytes")

    def refresh_table(self) -> None:
        self.refresh_info()
        db_path = self._db_path()
        table_name = self.table_select.currentText()
        if table_name not in DB_TABLE_WHITELIST:
            self._append("不允许查看该表。")
            return
        if not db_path.exists():
            self._append("数据库文件不存在。")
            return
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
                exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
                if not exists:
                    self._append(f"表不存在：{table_name}")
                    self.table.setRowCount(0)
                    self.table.setColumnCount(0)
                    return
                cursor = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 200')
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description or []]
            self.table.setColumnCount(len(columns))
            self.table.setHorizontalHeaderLabels(columns)
            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    self.table.setItem(r, c, QTableWidgetItem(str(value) if value is not None else ""))
            self.table.resizeColumnsToContents()
            self._append(f"已读取 {table_name}，{len(rows)} 行。")
        except Exception as exc:
            self._append(f"读取失败：{exc}")

    def _append(self, text: str) -> None:
        self.output.append(text)
        self.context.log(text)
