# Lightweight binary protocol

The clip node uses a compact binary frame for BLE/GATT payloads and mock test injection. It does not parse JSON and does not carry phone numbers, user data, parcel details, or cloud sync data.

## Frame format

| Byte | Field | Description |
| --- | --- | --- |
| 0 | `0xA5` | Fixed frame header |
| 1 | `cmd` or `event` | Command/event id |
| 2 | `len` | Payload length, max 16 bytes |
| 3..N | `payload` | Optional payload |
| Last | `checksum` | XOR from header through payload |

## Commands

| Value | Name | Behavior |
| --- | --- | --- |
| `0x01` | `PING` | Reply with `PONG` |
| `0x02` | `WAKE_TAG` | Enter `alerting`, drive RGB finding indication, auto-stop after 30 seconds. In the current battery-powered validation build, buzzer output is intentionally disabled. |
| `0x03` | `STOP_ALERT` | Turn off RGB indication and return to `bound` or `idle`. Buzzer remains disabled in the current battery-powered validation build. |
| `0x04` | `SET_BINDING` | Store a short binding token, then enter `bound` |
| `0x05` | `CLEAR_BINDING` | Clear local binding token and enter `idle` |
| `0x06` | `READ_STATUS` | Sample battery and report state |

## Events

| Value | Name |
| --- | --- |
| `0x81` | `BOOT` |
| `0x82` | `COMMAND_ACK` |
| `0x83` | `CLIP_REMOVED` |
| `0x84` | `CLIP_RETURNED` |
| `0x85` | `BATTERY_LOW` |
| `0x86` | `BATTERY_STATE_CHANGED` |
| `0x87` | `STATUS_REPORT` |
| `0x88` | `PONG` |

## Stored data boundary

The clip firmware may retain only:

- `tag_id`
- `binding_token` or a short token/hash
- `device_config`
- `last_state`

User permissions, parcel database records, phone numbers, pickup flow, and cloud synchronization remain in the gateway/server domains.
