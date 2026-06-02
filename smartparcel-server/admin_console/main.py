from __future__ import annotations

from admin_console.api_client import ApiClient
from admin_console.menu import Menu


def main() -> None:
    Menu(ApiClient()).run()


if __name__ == '__main__':
    main()
