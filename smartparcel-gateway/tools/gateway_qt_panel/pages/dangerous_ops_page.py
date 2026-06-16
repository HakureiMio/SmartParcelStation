from __future__ import annotations

import json
import shutil
from datetime import datetime

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget

from app_config import resolve_gateway_path
from env_editor import backup_file, load_env


class DangerousOpsPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        layout = QVBoxLayout(self)
        warning = QLabel("危险操作区：本页不提供删除数据库、清空业务数据、重建数据库、修改系统网络或蓝牙权限等破坏性操作。")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        buttons = QHBoxLayout()
        for text, slot in [
            ("备份 .env", self.backup_env),
            ("备份 SQLite 数据库", self.backup_db),
            ("导出调试报告", self.export_report),
            ("打开项目目录", self.open_project_dir),
        ]:
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

    def backup_env(self) -> None:
        if not self.context.paths.env_path.exists():
            self._append(".env 不存在，无法备份。")
            return
        backup = backup_file(self.context.paths.env_path)
        self._append(f".env 已备份：{backup}")

    def backup_db(self) -> None:
        env = load_env(self.context.paths.env_path)
        db_path = resolve_gateway_path(self.context.paths.gateway_dir, env.get("SQLITE_PATH"))
        if not db_path.exists():
            self._append("SQLite 数据库不存在，无法备份。")
            return
        if QMessageBox.question(self, "确认备份", f"将备份数据库文件：{db_path}\n是否继续？") != QMessageBox.Yes:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = db_path.with_name(f"{db_path.name}.bak.{timestamp}")
        shutil.copy2(db_path, backup)
        self._append(f"SQLite 数据库已备份：{backup}")

    def export_report(self) -> None:
        env = load_env(self.context.paths.env_path)
        safe_env = {k: ("********" if "SECRET" in k or "PASSWORD" in k or "TOKEN" in k else v) for k, v in env.items()}
        report = {
            "gateway_dir": str(self.context.paths.gateway_dir),
            "env_exists": self.context.paths.env_path.exists(),
            "env": safe_env,
        }
        report_path = self.context.paths.gateway_dir / f"qt-panel-debug-report-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append(f"调试报告已导出：{report_path}")

    def open_project_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.gateway_dir)))

    def _append(self, text: str) -> None:
        self.output.append(text)
        self.context.log(text)
