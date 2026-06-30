"""
Synchronous BLE command adapter that bridges RealBleTagService (async)
to the BleService (sync) interface used by AccessControlService.

This is the ONLY production path for access control BLE operations.
"""

from __future__ import annotations

import asyncio
from typing import Callable

from loguru import logger

from gateway.services.ble.real import RealBleTagService
from gateway.services.ble_service import BleService


class RealBleCommandService(BleService):
    """Synchronous adapter wrapping the real async BLE tag service.

    Uses asyncio.run() internally to bridge async → sync.
    Accepts a lookup function to resolve tag_id → ble_address.
    """

    def __init__(self, address_lookup: Callable[[str], str | None] | None = None):
        self._real = RealBleTagService()
        self._address_lookup = address_lookup

    def _resolve_address(self, tag_id: str) -> str:
        """Resolve a tag_id to a BLE address. Falls back to using tag_id as-is."""
        if self._address_lookup:
            addr = self._address_lookup(tag_id)
            if addr:
                return addr
        return tag_id

    def _run(self, coro):
        """Run an async coroutine synchronously, catching all errors."""
        try:
            return asyncio.run(coro)
        except Exception as exc:
            logger.warning("RealBleCommandService async error: {}", exc)
            return {"ok": False, "backend": "real", "error": "async_run_failed", "message": str(exc)}

    # ------------------------------------------------------------------
    # BleService interface
    # ------------------------------------------------------------------

    def tag_wake(
        self,
        tag_id: str,
        led_color: str = "BLUE",
        blink_pattern: str = "SLOW",
        beep_pattern: str = "SHORT_INTERVAL",
        duration_sec: int = 30,
        pickup_session_id: str | None = None,
    ) -> dict:
        address = self._resolve_address(tag_id)
        result = self._run(self._real.wake_tag(address, led_color, duration_sec))
        result["tag_id"] = tag_id
        result["action"] = "TAG_WAKE"
        result["result"] = "OK" if result.get("ok") else "FAILED"
        result["pickup_session_id"] = pickup_session_id
        return result

    def tag_stop(self, tag_id: str, pickup_session_id: str | None = None) -> dict:
        address = self._resolve_address(tag_id)
        result = self._run(self._real.stop_alert(address))
        result["tag_id"] = tag_id
        result["action"] = "TAG_STOP"
        result["result"] = "OK" if result.get("ok") else "FAILED"
        result["pickup_session_id"] = pickup_session_id
        return result

    def tag_status_query(self, tag_id: str) -> dict:
        address = self._resolve_address(tag_id)
        result = self._run(self._real.read_status(address))
        result["tag_id"] = tag_id
        result["action"] = "TAG_STATUS_QUERY"
        result["result"] = "OK" if result.get("ok") else "FAILED"
        return result
