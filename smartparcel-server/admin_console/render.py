from __future__ import annotations

from typing import Any


def print_rows(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        print('(empty)')
        return
    widths = {
        col: max(len(col), *(len(str(row.get(col, ''))) for row in rows))
        for col in columns
    }
    print(' | '.join(col.ljust(widths[col]) for col in columns))
    print('-+-'.join('-' * widths[col] for col in columns))
    for row in rows:
        print(' | '.join(str(row.get(col, '')).ljust(widths[col]) for col in columns))


def print_block(title: str, data: Any) -> None:
    print(f'\n{title}')
    print('-' * len(title))
    if isinstance(data, list):
        for item in data:
            print(item)
    else:
        print(data)
