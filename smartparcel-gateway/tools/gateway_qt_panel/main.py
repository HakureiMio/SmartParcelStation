from __future__ import annotations

import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QListWidget, QMainWindow, QSplitter, QStackedWidget

from app_config import get_paths
from pages.ble_page import BlePage
from pages.config_page import ConfigPage
from pages.dangerous_ops_page import DangerousOpsPage
from pages.dashboard_page import DashboardPage
from pages.database_page import DatabasePage
from pages.first_boot_page import FirstBootPage
from pages.local_api_page import LocalApiPage
from pages.logs_page import LogsPage
from pages.server_mqtt_page import ServerMqttPage
from pages.system_service_page import SystemServicePage


class AppContext(QObject):
    log_message = Signal(str)

    def __init__(self):
        super().__init__()
        self.paths = get_paths()

    def log(self, message: str) -> None:
        self.log_message.emit(message)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartParcel Gateway 本地维护面板")
        self.resize(1180, 760)
        self.context = AppContext()

        splitter = QSplitter()
        self.nav = QListWidget()
        self.nav.setMaximumWidth(230)
        self.stack = QStackedWidget()
        splitter.addWidget(self.nav)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self._add_page("总览", DashboardPage(self.context))
        self._add_page("初期部署", FirstBootPage(self.context))
        self._add_page("底层配置", ConfigPage(self.context))
        self._add_page("Server / MQTT", ServerMqttPage(self.context))
        self._add_page("BLE 设置", BlePage(self.context))
        self._add_page("本地数据库", DatabasePage(self.context))
        self._add_page("Local API", LocalApiPage(self.context))
        self._add_page("系统服务", SystemServicePage(self.context))
        self._add_page("日志", LogsPage(self.context))
        self._add_page("危险操作", DangerousOpsPage(self.context))

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

    def _add_page(self, name: str, widget) -> None:
        self.nav.addItem(name)
        self.stack.addWidget(widget)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
