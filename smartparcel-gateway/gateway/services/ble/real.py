from __future__ import annotations

import asyncio
import re
from contextlib import suppress

from gateway.services.ble.base import BleTagServiceBase
from gateway.services.ble.protocol import (
    CLIP_CMD_READ_STATUS,
    CLIP_CMD_STOP_ALERT,
    CLIP_CMD_WAKE_TAG,
    CLIP_EVT_STATUS_REPORT,
    build_command,
    parse_event,
)

SPS_TAG_SERVICE_UUID = "8f7e9000-5d1b-4c2f-9e8a-5f2f5b7b0001"
SPS_TAG_CMD_WRITE_UUID = "8f7e9001-5d1b-4c2f-9e8a-5f2f5b7b0001"
SPS_TAG_EVENT_NOTIFY_UUID = "8f7e9002-5d1b-4c2f-9e8a-5f2f5b7b0001"
SPS_TAG_STATUS_READ_UUID = "8f7e9003-5d1b-4c2f-9e8a-5f2f5b7b0001"

FACTORY_NAME_RE = re.compile(r"^SPS-[A-Z0-9]{2,8}-[0-9]{8}-[0-9]{4,8}$")
LEGACY_NAME_RE = re.compile(r"^SPS-TAG-[0-9A-Fa-f]{4,8}$")


class RealBleTagService(BleTagServiceBase):
    backend = "real"

    async def scan_tags(self, timeout_sec: float = 5.0) -> list[dict]:
        try:
            from bleak import BleakScanner
        except ImportError:
            return [self._error("bleak_not_installed")]

        try:
            devices = await BleakScanner.discover(timeout=timeout_sec, return_adv=True)
        except Exception as exc:
            return [self._error("scan_failed", str(exc))]

        items: list[dict] = []
        for address, item in devices.items():
            device, adv = item
            name = device.name or adv.local_name or ""
            if not (FACTORY_NAME_RE.match(name) or LEGACY_NAME_RE.match(name)):
                continue
            items.append(
                {
                    "ble_name": name,
                    "ble_address": address,
                    "rssi": getattr(adv, "rssi", None),
                }
            )
        return items

    async def connect_tag(self, ble_address: str) -> dict:
        try:
            from bleak import BleakClient
        except ImportError:
            return self._error("bleak_not_installed", ble_address=ble_address)

        try:
            async with BleakClient(ble_address) as client:
                if not client.is_connected:
                    return self._error("connect_failed", ble_address=ble_address)
            return self._ok(ble_address, "connect", "connected")
        except Exception as exc:
            return self._error("connect_failed", str(exc), ble_address)

    async def disconnect_tag(self, ble_address: str) -> dict:
        return self._ok(ble_address, "disconnect", "short connection closed")

    async def wake_tag(self, ble_address: str, color: str = "BLUE", duration_sec: int = 30) -> dict:
        payload = bytes([self._color_code(color), max(0, min(duration_sec, 255))])
        result = await self._write_command(ble_address, CLIP_CMD_WAKE_TAG, payload, "wake", wait_status=False)
        if result.get("ok"):
            result.update({"color": color, "duration_sec": duration_sec})
        return result

    async def stop_alert(self, ble_address: str) -> dict:
        return await self._write_command(ble_address, CLIP_CMD_STOP_ALERT, b"", "stop", wait_status=False)

    async def read_status(self, ble_address: str) -> dict:
        return await self._write_command(ble_address, CLIP_CMD_READ_STATUS, b"", "read_status", wait_status=True)

    async def _write_command(self, ble_address: str, cmd: int, payload: bytes, action: str, wait_status: bool) -> dict:
        try:
            from bleak import BleakClient
        except ImportError:
            return self._error("bleak_not_installed", ble_address=ble_address)

        event_future: asyncio.Future | None = None

        def on_notify(_sender: int, data: bytearray) -> None:
            nonlocal event_future
            if event_future is None or event_future.done():
                return
            try:
                event_future.set_result(parse_event(bytes(data)))
            except ValueError as exc:
                event_future.set_exception(exc)

        try:
            async with BleakClient(ble_address) as client:
                if wait_status:
                    event_future = asyncio.get_running_loop().create_future()
                    with suppress(Exception):
                        await client.start_notify(SPS_TAG_EVENT_NOTIFY_UUID, on_notify)
                await client.write_gatt_char(SPS_TAG_CMD_WRITE_UUID, build_command(cmd, payload), response=True)
                await asyncio.sleep(0.2)
                result = self._ok(ble_address, action, f"{action.upper()} command sent")
                if wait_status and event_future is not None:
                    try:
                        event = await asyncio.wait_for(event_future, timeout=2.0)
                        result["event"] = {
                            "event": event["event"],
                            "payload_hex": event["payload"].hex(),
                        }
                        if event["event"] == CLIP_EVT_STATUS_REPORT:
                            self._merge_status_payload(result, event["payload"])
                    except Exception:
                        result["status_query_sent"] = True
                    with suppress(Exception):
                        await client.stop_notify(SPS_TAG_EVENT_NOTIFY_UUID)
                return result
        except Exception as exc:
            return self._error("command_failed", str(exc), ble_address)

    def _merge_status_payload(self, result: dict, payload: bytes) -> None:
        if len(payload) >= 6:
            result["clip_state"] = payload[0]
            result["battery_state"] = payload[1]
            result["battery_mv"] = payload[4] | (payload[5] << 8)

    def _color_code(self, color: str) -> int:
        return {"BLUE": 1, "GREEN": 2, "RED": 3, "WHITE": 4}.get(color.upper(), 1)

    def _ok(self, ble_address: str, action: str, message: str) -> dict:
        return {
            "ok": True,
            "backend": self.backend,
            "ble_address": ble_address,
            "action": action,
            "message": message,
        }

    def _error(self, error: str, message: str | None = None, ble_address: str | None = None) -> dict:
        result = {"ok": False, "backend": self.backend, "error": error}
        if message:
            result["message"] = message
        if ble_address:
            result["ble_address"] = ble_address
        return result
