from __future__ import annotations

from abc import ABC, abstractmethod


class BleService(ABC):
    @abstractmethod
    def tag_wake(self, tag_id: str) -> dict: ...

    @abstractmethod
    def tag_stop(self, tag_id: str) -> dict: ...

    @abstractmethod
    def tag_status_query(self, tag_id: str) -> dict: ...
