from __future__ import annotations

import random
from datetime import datetime

from gateway.services.ble_service import BleService


class MockBleService(BleService):
    def tag_wake(self, tag_id: str) -> dict:
        return {"tag_id": tag_id, "action": "TAG_WAKE", "result": "OK", "ts": datetime.utcnow().isoformat()}

    def tag_stop(self, tag_id: str) -> dict:
        return {"tag_id": tag_id, "action": "TAG_STOP", "result": "OK", "ts": datetime.utcnow().isoformat()}

    def tag_status_query(self, tag_id: str) -> dict:
        return {
            "tag_id": tag_id,
            "action": "TAG_STATUS_QUERY",
            "result": "OK",
            "battery_level": random.randint(40, 99),
            "ts": datetime.utcnow().isoformat(),
        }
