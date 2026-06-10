from __future__ import annotations

from gateway.core.config import get_settings
from gateway.services.ble.base import BleTagServiceBase
from gateway.services.ble.mock import MockBleTagService
from gateway.services.ble.real import RealBleTagService


def get_ble_tag_service() -> BleTagServiceBase:
    backend = (get_settings().ble_backend or "mock").strip().lower()
    if backend == "real":
        return RealBleTagService()
    return MockBleTagService()
