from __future__ import annotations

from abc import ABC, abstractmethod


class BleService(ABC):
    @abstractmethod
    def tag_wake(
        self,
        tag_id: str,
        led_color: str = "BLUE",
        blink_pattern: str = "SLOW",
        beep_pattern: str = "SHORT_INTERVAL",
        duration_sec: int = 30,
        pickup_session_id: str | None = None,
    ) -> dict: ...

    @abstractmethod
    def tag_stop(self, tag_id: str, pickup_session_id: str | None = None) -> dict: ...

    @abstractmethod
    def tag_status_query(self, tag_id: str) -> dict: ...
