"""
Legacy mock BLE service (moved from gateway/services/mock_ble_service.py).

This file is retained for historical reference and testing only.
It is NOT imported by any production code path.
"""

from __future__ import annotations

import random
from datetime import datetime

from gateway.services.ble_service import BleService


class MockBleService(BleService):
    def tag_wake(
        self,
        tag_id: str,
        led_color: str = "BLUE",
        blink_pattern: str = "SLOW",
        beep_pattern: str = "SHORT_INTERVAL",
        duration_sec: int = 30,
        pickup_session_id: str | None = None,
    ) -> dict:
        return {
            "tag_id": tag_id,
            "action": "TAG_WAKE",
            "result": "OK",
            "led_color": led_color,
            "blink_pattern": blink_pattern,
            "beep_pattern": beep_pattern,
            "duration_sec": duration_sec,
            "pickup_session_id": pickup_session_id,
            "ts": datetime.utcnow().isoformat(),
        }

    def tag_stop(self, tag_id: str, pickup_session_id: str | None = None) -> dict:
        return {"tag_id": tag_id, "action": "TAG_STOP", "result": "OK", "pickup_session_id": pickup_session_id, "ts": datetime.utcnow().isoformat()}

    def tag_status_query(self, tag_id: str) -> dict:
        return {
            "tag_id": tag_id,
            "action": "TAG_STATUS_QUERY",
            "result": "OK",
            "battery_level": random.randint(40, 99),
            "ts": datetime.utcnow().isoformat(),
        }
