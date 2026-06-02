from __future__ import annotations

import locale
import sys


def setup_utf8_console() -> None:
    if sys.platform != 'win32':
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    try:
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    try:
        locale.setlocale(locale.LC_ALL, '')
    except Exception:
        pass
