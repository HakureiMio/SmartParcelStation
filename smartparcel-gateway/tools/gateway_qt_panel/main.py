from __future__ import annotations

import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QListWidget,
    QMainWindow,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QToolBar,
)

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


WINDOW_SIZE_PRESETS: list[tuple[str, int, int]] = [
    ("800 x 480", 800, 480),
    ("1024 x 600", 1024, 600),
    ("1280 x 720", 1280, 720),
    ("1366 x 768", 1366, 768),
    ("1920 x 1080", 1920, 1080),
]
DEFAULT_WINDOW_SIZE = (1024, 600)


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
        self.resize(*DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(800, 480)
        self.context = AppContext()
        self._build_size_toolbar()

        splitter = QSplitter()
        self.nav = QListWidget()
        self.nav.setMaximumWidth(180)
        self.stack = QStackedWidget()
        splitter.addWidget(self.nav)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([165, DEFAULT_WINDOW_SIZE[0] - 165])
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

    def _build_size_toolbar(self) -> None:
        toolbar = QToolBar("窗口尺寸")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addWidget(QLabel("窗口尺寸："))

        self.size_combo = QComboBox()
        for label, width, height in WINDOW_SIZE_PRESETS:
            self.size_combo.addItem(label, (width, height))
        default_index = next(
            (
                index
                for index, (_, width, height) in enumerate(WINDOW_SIZE_PRESETS)
                if (width, height) == DEFAULT_WINDOW_SIZE
            ),
            0,
        )
        self.size_combo.setCurrentIndex(default_index)
        self.size_combo.currentIndexChanged.connect(self.apply_size_preset)
        toolbar.addWidget(self.size_combo)

    def apply_size_preset(self, index: int) -> None:
        size = self.size_combo.itemData(index)
        if not size:
            return
        width, height = size
        self.resize(width, height)
        self.context.log(f"窗口尺寸已切换为 {width} x {height}")

    def _add_page(self, name: str, widget) -> None:
        self.nav.addItem(name)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        self.stack.addWidget(scroll)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
