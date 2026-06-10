from __future__ import annotations

from datetime import datetime

from gateway.services.ble.base import BleTagServiceBase


class MockBleTagService(BleTagServiceBase):
    backend = "mock"

    async def scan_tags(self, timeout_sec: float = 5.0) -> list[dict]:
        return [
            {
                "ble_name": "SPS-F01-20260610-0001",
                "ble_address": "MOCK:TAG:FACTORY:0001",
                "rssi": -43,
            },
            {
                "ble_name": "SPS-TAG-0001",
                "ble_address": "MOCK:TAG:0001",
                "rssi": -45,
            },
        ]

    async def connect_tag(self, ble_address: str) -> dict:
        return self._ok(ble_address, "connect", "mock connected")

    async def disconnect_tag(self, ble_address: str) -> dict:
        return self._ok(ble_address, "disconnect", "mock disconnected")

    async def wake_tag(self, ble_address: str, color: str = "BLUE", duration_sec: int = 30) -> dict:
        result = self._ok(ble_address, "wake", "mock WAKE_TAG sent")
        result.update({"color": color, "duration_sec": duration_sec})
        return result

    async def stop_alert(self, ble_address: str) -> dict:
        return self._ok(ble_address, "stop", "mock STOP_ALERT sent")

    async def read_status(self, ble_address: str) -> dict:
        result = self._ok(ble_address, "read_status", "mock READ_STATUS sent")
        result.update({"status_query_sent": True, "battery_mv": 2980, "battery_level": 82})
        return result

    def _ok(self, ble_address: str, action: str, message: str) -> dict:
        return {
            "ok": True,
            "backend": self.backend,
            "ble_address": ble_address,
            "action": action,
            "message": message,
            "ts": datetime.utcnow().isoformat(),
        }
