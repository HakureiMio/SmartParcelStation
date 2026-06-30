from __future__ import annotations

from gateway.core.config import get_settings
from gateway.services.ble.base import BleTagServiceBase
from gateway.services.ble.real import RealBleTagService


class BleBackendError(Exception):
    """Raised when the configured BLE backend is not available."""


def get_ble_tag_service() -> BleTagServiceBase:
    """Return the BLE tag service implementation.

    Only 'real' is accepted in production. Any other value raises BleBackendError.
    Mock is never used as a fallback.
    """
    backend = (get_settings().ble_backend or "real").strip().lower()
    if backend == "real":
        return RealBleTagService()
    raise BleBackendError(
        f"BLE_BACKEND={backend!r} is not supported. "
        "Set BLE_BACKEND=real and ensure bleak is installed and a Bluetooth adapter is available."
    )
