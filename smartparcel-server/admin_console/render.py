from __future__ import annotations

import unicodedata
from typing import Any


def display_width(text: str) -> int:
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in {'F', 'W'} else 1
    return width


def pad_display(text: str, width: int) -> str:
    return text + ' ' * max(width - display_width(text), 0)


def display_value(value: Any) -> str:
    if value is None:
        return '-'
    if isinstance(value, bool):
        return '是' if value else '否'
    return str(value)


def print_rows(rows: list[dict[str, Any]], columns: list[str], headers: dict[str, str] | None = None) -> None:
    if not rows:
        print('暂无数据。')
        return
    headers = headers or {}
    widths = {
        col: max(display_width(headers.get(col, col)), *(display_width(display_value(row.get(col, ''))) for row in rows))
        for col in columns
    }
    print(' | '.join(pad_display(headers.get(col, col), widths[col]) for col in columns))
    print('-+-'.join('-' * widths[col] for col in columns))
    for row in rows:
        print(' | '.join(pad_display(display_value(row.get(col, '')), widths[col]) for col in columns))


def print_block(title: str, lines: list[str]) -> None:
    print(f'\n{title}')
    print('-' * display_width(title))
    for line in lines:
        print(line)
