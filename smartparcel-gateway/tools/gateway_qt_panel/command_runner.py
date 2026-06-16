from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal


class CommandRunner(QObject):
    output = Signal(str)
    finished = Signal(int)

    def __init__(self, working_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self.working_dir = working_dir
        self.process: QProcess | None = None

    def run(self, args: list[str]) -> None:
        if self.process and self.process.state() != QProcess.NotRunning:
            self.output.emit("已有命令正在执行，请稍后再试。")
            return
        self.process = QProcess(self)
        self.process.setWorkingDirectory(str(self.working_dir))
        self.process.setProgram(args[0])
        self.process.setArguments(args[1:])
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.output.emit(f"$ {' '.join(self._masked_args(args))}")
        self.process.start()

    def _masked_args(self, args: list[str]) -> list[str]:
        secret_flags = {"--registration-token", "--mqtt-password", "--gateway-secret", "--password", "--token"}
        masked: list[str] = []
        hide_next = False
        for arg in args:
            if hide_next:
                masked.append("********")
                hide_next = False
                continue
            if arg in secret_flags:
                masked.append(arg)
                hide_next = True
                continue
            lowered = arg.lower()
            if any(name in lowered for name in ["password=", "secret=", "token="]):
                key, _sep, _value = arg.partition("=")
                masked.append(f"{key}=********")
                continue
            masked.append(arg)
        return masked

    def _read_output(self) -> None:
        if not self.process:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output.emit(data.rstrip())

    def _finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self.output.emit(f"命令结束，退出码：{exit_code}")
        self.finished.emit(exit_code)
