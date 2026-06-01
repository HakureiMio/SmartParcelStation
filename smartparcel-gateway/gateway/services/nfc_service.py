from __future__ import annotations

from abc import ABC, abstractmethod


class NfcService(ABC):
    @abstractmethod
    def handle_card(self, card_uid: str) -> dict: ...
