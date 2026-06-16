from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def backup_file(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak.{timestamp}")
    if path.exists():
        shutil.copy2(path, backup_path)
    else:
        backup_path.write_text("", encoding="utf-8")
    return backup_path


def save_env(path: Path, updates: dict[str, str], allowed_keys: list[str] | set[str]) -> Path:
    allowed = set(allowed_keys)
    allowed_order = list(allowed_keys)
    filtered = {key: str(value) for key, value in updates.items() if key in allowed}
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = backup_file(path)

    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output: list[str] = []

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            output.append(raw_line)
            continue
        key = raw_line.split("=", 1)[0].strip()
        if key in filtered:
            output.append(f"{key}={filtered[key]}")
            seen.add(key)
        else:
            output.append(raw_line)

    for key in allowed_order:
        if key in filtered and key not in seen:
            output.append(f"{key}={filtered[key]}")

    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    return backup_path
