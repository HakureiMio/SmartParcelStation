from __future__ import annotations

CLIP_PROTO_FRAME_HEADER = 0xA5
CLIP_PROTO_MAX_PAYLOAD_LEN = 16

CLIP_CMD_PING = 0x01
CLIP_CMD_WAKE_TAG = 0x02
CLIP_CMD_STOP_ALERT = 0x03
CLIP_CMD_SET_BINDING = 0x04
CLIP_CMD_CLEAR_BINDING = 0x05
CLIP_CMD_READ_STATUS = 0x06

CLIP_EVT_BOOT = 0x81
CLIP_EVT_COMMAND_ACK = 0x82
CLIP_EVT_CLIP_REMOVED = 0x83
CLIP_EVT_CLIP_RETURNED = 0x84
CLIP_EVT_BATTERY_LOW = 0x85
CLIP_EVT_BATTERY_STATE_CHANGED = 0x86
CLIP_EVT_STATUS_REPORT = 0x87
CLIP_EVT_PONG = 0x88


def _xor_checksum(data: bytes) -> int:
    value = 0
    for item in data:
        value ^= item
    return value


def build_command(cmd: int, payload: bytes = b"") -> bytes:
    if len(payload) > CLIP_PROTO_MAX_PAYLOAD_LEN:
        raise ValueError("payload too large")
    body = bytes([CLIP_PROTO_FRAME_HEADER, cmd & 0xFF, len(payload)]) + payload
    return body + bytes([_xor_checksum(body)])


def parse_event(frame: bytes) -> dict:
    if len(frame) < 4:
        raise ValueError("frame too short")
    if frame[0] != CLIP_PROTO_FRAME_HEADER:
        raise ValueError("invalid frame header")
    payload_len = frame[2]
    expected_len = 4 + payload_len
    if len(frame) != expected_len:
        raise ValueError("invalid frame length")
    if payload_len > CLIP_PROTO_MAX_PAYLOAD_LEN:
        raise ValueError("payload too large")
    checksum = _xor_checksum(frame[: 3 + payload_len])
    if checksum != frame[3 + payload_len]:
        raise ValueError("invalid checksum")
    return {
        "event": frame[1],
        "payload_len": payload_len,
        "payload": frame[3 : 3 + payload_len],
        "raw": frame,
    }
