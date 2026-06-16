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
