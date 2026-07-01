from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def check_systemd_service(name: str) -> bool:
    if shutil.which("systemctl") is None:
        return False
    result = subprocess.run(["systemctl", "status", name, "--no-pager"], capture_output=True, text=True, timeout=8)
    return result.returncode in {0, 3}


def get_systemd_status(name: str) -> str:
    if shutil.which("systemctl") is None:
        return "未检测到 systemctl，当前环境可能不是 systemd Linux。"
    result = subprocess.run(["systemctl", "status", name, "--no-pager"], capture_output=True, text=True, timeout=8)
    return (result.stdout + result.stderr).strip() or f"systemctl 退出码：{result.returncode}"


def generate_service_template(project_dir: Path, python_path: Path) -> str:
    return f"""[Unit]
Description=SmartParcel Gateway Local Service
After=network.target bluetooth.target

[Service]
Type=simple
WorkingDirectory={project_dir}
Environment=PYTHONUNBUFFERED=1
ExecStart={python_path} -m gateway.main run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


def gateway_qt_autostart_script(project_dir: Path) -> Path:
    return project_dir / "scripts" / "gateway_qt_autostart.sh"


def is_gateway_qt_autostart_enabled(project_dir: Path) -> bool:
    script = gateway_qt_autostart_script(project_dir)
    if not script.exists() or shutil.which("bash") is None:
        return False
    result = subprocess.run(
        ["bash", str(script), "status"], capture_output=True, text=True, timeout=10
    )
    return result.returncode == 0


def set_gateway_qt_autostart(project_dir: Path, enabled: bool) -> str:
    script = gateway_qt_autostart_script(project_dir)
    if not script.exists():
        return f"未找到自动启动脚本：{script}"
    if shutil.which("bash") is None:
        return "未检测到 bash；自动启动开关适用于 Linux 桌面环境。"
    action = "enable" if enabled else "disable"
    result = subprocess.run(
        ["bash", str(script), action], capture_output=True, text=True, timeout=25
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return output or f"自动启动设置失败，退出码：{result.returncode}"
    return output or ("已启用自动启动。" if enabled else "已关闭自动启动。")
