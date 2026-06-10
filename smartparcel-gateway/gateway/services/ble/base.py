from __future__ import annotations

from abc import ABC, abstractmethod


class BleTagServiceBase(ABC):
    @abstractmethod
    async def scan_tags(self, timeout_sec: float = 5.0) -> list[dict]: ...

    @abstractmethod
    async def connect_tag(self, ble_address: str) -> dict: ...

    @abstractmethod
    async def disconnect_tag(self, ble_address: str) -> dict: ...

    @abstractmethod
    async def wake_tag(self, ble_address: str, color: str = "BLUE", duration_sec: int = 30) -> dict: ...

    @abstractmethod
    async def stop_alert(self, ble_address: str) -> dict: ...

    @abstractmethod
    async def read_status(self, ble_address: str) -> dict: ...
