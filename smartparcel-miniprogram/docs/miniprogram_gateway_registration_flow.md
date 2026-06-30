# Mini Program — Gateway Registration Flow

> **Version:** 1.0
> **Date:** 2026-06-30
> **Scope:** Employee (staff) gateway registration from scratch via WeChat Mini Program.

## Overview

This document describes the complete flow for an employee to register a new SmartParcel gateway through the WeChat Mini Program. The flow covers:

1. Employee login (real server auth)
2. Server-side binding parameter preparation
3. Connecting to the gateway hotspot
4. Reading the gateway provisioning status
5. Pushing binding parameters to the gateway
6. Polling for gateway-server handshake completion
7. Saving a short-lived local session token
8. Using the local session for BLE tag management and other gateway operations

## Network Scenarios

### Scenario A — Hotspot has internet access

The employee's phone connects to the gateway hotspot, and the hotspot provides internet access to reach the VPS server. The entire flow happens in one sequence.

### Scenario B — Hotspot has no internet

1. Phone on cellular / normal Wi-Fi → request binding params from server
2. Switch to gateway hotspot → read provisioning status, push binding params, poll verify

The mini program UI supports both scenarios explicitly with a selector in Step 1.

## Step-by-step Flow

### Step 1 — Verify employee identity and server connection

- Page: `pages/staff-gateway-register/staff-gateway-register`
- Call `authService.requireRole('staff')`
- Call `GET /api/v1/health` to verify server is reachable
- If unreachable, show error — do NOT proceed

### Step 2 — Enter / confirm gateway information

Employee provides or confirms:
- `gateway_serial` (e.g. `SPS-GW-0001`)
- `gateway_device_id` (optional, e.g. `GWDEV-xxxx`)
- `station_id` (e.g. `1`)
- `requested_gateway_code` (optional, e.g. `GW001`)

These can be auto-filled later from provisioning status.

### Step 3 — Request binding parameters from server

**Request:**
```
POST /api/v1/gateways/provisioning/prepare
Authorization: Bearer <staff_token>
Content-Type: application/json

{
  "gateway_device_id": "GWDEV-xxxx",
  "gateway_serial": "SPS-GW-xxxx",
  "station_id": "1",
  "requested_gateway_code": "GW001"
}
```

**Response (server MUST NOT return gateway_secret):**
```json
{
  "ok": true,
  "server_base_url": "https://api.example.com",
  "gateway_code": "GW001",
  "station_id": "1",
  "registration_token": "short-lived-token",
  "mqtt_host": "api.example.com",
  "mqtt_port": 1883,
  "mqtt_tls_enabled": false,
  "config_version": 1,
  "expires_at": "2026-06-30T12:00:00Z"
}
```

**Security:** If the server response contains `gateway_secret`, the mini program treats this as a backend error and does NOT store or display the value.

### Step 4 — Connect to gateway hotspot

- Display expected SSID: `SmartParcel-GW-XXXX` (or actual from provisioning status)
- Employee manually connects via system Wi-Fi settings
- Gateway provisioning address: `http://192.168.4.1:19000` (default)

### Step 5 — Read gateway provisioning status

**Request:**
```
GET http://192.168.4.1:19000/local/provisioning/status
```

**Response:**
```json
{
  "binding_status": "UNBOUND",
  "gateway_device_id": "GWDEV-xxxx",
  "gateway_serial": "SPS-GW-xxxx",
  "ap_ssid": "SmartParcel-GW-0001",
  "local_ip": "192.168.4.1",
  "gateway_code": null,
  "station_id": null
}
```

If the gateway is already `BOUND`, the UI warns the user before proceeding.

### Step 6 — Push binding parameters to gateway

**Request:**
```
POST http://192.168.4.1:19000/local/provisioning/bind
Content-Type: application/json

{
  "server_base_url": "https://api.example.com",
  "gateway_code": "GW001",
  "station_id": "1",
  "registration_token": "short-lived-token",
  "mqtt_host": "api.example.com",
  "mqtt_port": 1883,
  "mqtt_tls_enabled": false,
  "config_version": 1,
  "expires_at": "2026-06-30T12:00:00Z"
}
```

**Security pre-checks (mini program side):**
- `server_base_url` must be HTTPS (unless `allowInsecureServerHttpInDev` is true)
- `registration_token` must be present
- `gateway_code` and `station_id` must be present

**Security:** If the gateway response contains `gateway_secret`, it is stripped before any storage or display.

### Step 7 — Poll gateway verify

**Request (polled every 2 seconds):**
```
POST http://192.168.4.1:19000/local/provisioning/verify
```

**Response states:**
| binding_status | Description |
|---|---|
| `ACTIVATING` | Gateway is activating with server |
| `WRITING_CONFIG` | Writing configuration to flash |
| `HEARTBEAT_TO_SERVER` | Sending heartbeat to server |
| `BOUND` | Binding complete — success |
| `FAILED` | Binding failed — see error_code |

**Error codes:**
| error_code | Description |
|---|---|
| `SERVER_UNREACHABLE` | Gateway cannot reach the VPS server |
| `REGISTRATION_TOKEN_EXPIRED` | The registration token has expired |
| `GATEWAY_HEARTBEAT_FAILED` | Heartbeat handshake failed |
| `INVALID_GATEWAY_CODE` | Gateway code is invalid or already taken |
| `STATION_MISMATCH` | Station ID does not match |

### Step 8 — Save local session and complete

If the gateway returns a `local_session_token` in the bind/verify response, save it directly.

Otherwise, request one explicitly:

**Request:**
```
POST http://192.168.4.1:19000/local/provisioning/local-session
Content-Type: application/json

{
  "gateway_code": "GW001"
}
```

**Response:**
```json
{
  "ok": true,
  "local_session_token": "short-lived-session-token",
  "local_session_expires_at": "2026-07-01T12:00:00Z",
  "gateway_code": "GW001",
  "station_id": "1"
}
```

**Storage (via `local-session-service.js`):**
| Field | Stored |
|---|---|
| `gatewayBaseUrl` | ✅ Yes |
| `gatewayCode` | ✅ Yes |
| `stationId` | ✅ Yes |
| `localSessionToken` | ✅ Yes |
| `localSessionExpiresAt` | ✅ Yes |
| `boundAt` | ✅ Yes |
| `gateway_secret` | ❌ NEVER |
| `registration_token` | ❌ NEVER |
| `one_time_binding_token` | ❌ NEVER |
| `server admin token` | ❌ NEVER |

After saving, navigate to `pages/gateway-status/gateway-status`.

## API Contract — Server

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/health` | None | Health check |
| `POST` | `/api/v1/auth/login` | None | Login (returns Bearer token) |
| `POST` | `/api/v1/gateways/provisioning/prepare` | Bearer (staff) | Prepare gateway binding |
| `POST` | `/api/v1/gateways/provisioning/confirm` | Bearer (staff) | Confirm binding completion |
| `GET` | `/api/v1/stations` | Bearer (staff) | List staff-accessible stations |
| `POST` | `/api/v1/gateways/registration-tokens` | Bearer (staff) | Create registration token |
| `GET` | `/api/v1/gateways/registration-tokens` | Bearer (staff) | List registration tokens |

## API Contract — Gateway (Local)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/local/provisioning/status` | None | Provisioning state |
| `POST` | `/local/provisioning/bind` | None | Push server binding params |
| `POST` | `/local/provisioning/verify` | None | Poll binding result |
| `POST` | `/local/provisioning/local-session` | None* | Get local session token |
| `GET` | `/local/health` | None | Gateway health check |
| `POST` | `/local/tags/scan` | Bearer (local) | Scan BLE tags |
| `POST` | `/local/tags/register-from-ble` | Bearer (local) | Register a scanned tag |
| `GET` | `/local/tags` | Bearer (local) | List registered tags |
| `GET` | `/local/tags/{tag_id}` | Bearer (local) | Get tag details |
| `POST` | `/local/tags/{tag_id}/connect` | Bearer (local) | Connect to tag |
| `POST` | `/local/tags/{tag_id}/wake` | Bearer (local) | Wake / LED / buzzer |
| `POST` | `/local/tags/{tag_id}/stop` | Bearer (local) | Stop tag operation |
| `GET` | `/local/tags/{tag_id}/status` | Bearer (local) | Read tag status |
| `POST` | `/local/gate/access-card` | Bearer (local) | Gate/door access |

\* The `local-session` endpoint may be gated behind proof-of-binding (returned token from bind).

## BLE Tag Management — Authorization Flow

After gateway binding:

1. BLE tag management pages call gateway APIs with `Authorization: Bearer <local_session_token>`
2. If the local session is missing or expired → return `LOCAL_SESSION_MISSING`
3. Page shows "请先完成网关注册 / 授权" and offers a button to navigate to the registration page
4. No mock data is ever returned
5. No `MOCK:TAG` addresses are ever shown

## Sensitive Data Handling

### Fields that MUST be redacted in debug/log output:
- `gateway_secret`, `GATEWAY_SECRET`
- `registration_token`, `one_time_binding_token`
- `local_session_token`, `Authorization`
- `token`, `password`, `appsecret`, `secret`, `signature`
- `access_token`, `refresh_token`, `api_key`, `private_key`

### Fields NEVER stored in wx.storage:
- `gateway_secret`
- `registration_token` (discarded after use)
- `password`
- `server admin token`

### Fields stored in wx.storage:
- `sps_token` — Server Bearer token
- `sps_role` — client | staff
- `sps_user_id` — User ID
- `sps_display_name` — Display name
- `sps_station_id` — Primary station
- `sps_expires_at` — Token expiry
- `sps_gateway_local_session` — JSON with gatewayCode, stationId, localSessionToken (short-lived), expiresAt, boundAt

## Verification Checklist

After implementation, verify:

- [ ] Login fails with "server unreachable" instead of mock success
- [ ] No demo credentials pre-filled in login form
- [ ] No "演示登录成功" toast
- [ ] No "演示模式" anywhere in staff-home, gateway-status, BLE pages
- [ ] No `MOCK:TAG` addresses in BLE tag lists
- [ ] No mock NFC tag reads
- [ ] Staff workbench shows gateway binding status (unbound/offline/normal)
- [ ] Unauthorized gateway access → clear prompt to register
- [ ] Gateway registration flow: server → info → params → hotspot → status → bind → verify → session
- [ ] Scenario A and B supported
- [ ] Debug panel output is redacted (no tokens/secrets visible)
- [ ] Server prepare response with gateway_secret → refused
- [ ] Gateway bind response with gateway_secret → stripped
- [ ] wx.storage has no gateway_secret or registration_token
- [ ] BLE tag API calls include `Authorization: Bearer <local_session_token>`
- [ ] Local session expiry → auto-redirect to registration
