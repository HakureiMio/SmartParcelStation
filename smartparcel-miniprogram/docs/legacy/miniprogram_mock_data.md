# Legacy Mock Data (Archived)

> **Status:** REMOVED from production code.
> **Date:** 2026-06-30
> **Reason:** All mock/demo fallback logic has been removed from the mini program.
> The real gateway registration + server API flow is now required.

## Original mock-data.js locations

This file was previously at `services/mock-data.js` and was imported by:
- `services/server-api.js`
- `services/gateway-api.js`

## What was removed

The mock data file provided fake responses for:
- Gateway health checks
- Parcel lists (3 demo parcels)
- Notifications (3 demo notifications)
- Pickup status with mock gateway hints
- BLE tag scanning (mock tag addresses like `MOCK:TAG:FACTORY:0001`)
- Tag registration, connect, wake, stop, status operations
- Inbound parcel registration
- Tag binding
- Exception reporting
- NFC fast pickup confirmation

All functions returned `{ ok: true, source: 'mock', ... }` with fabricated data.

## Why removed

1. The mini program now uses real server APIs with Bearer token authentication.
2. Gateway business APIs require a valid local session token obtained through the provisioning flow.
3. Mock fallback hid real connectivity issues during development.
4. No mock gateway_secrets, tokens, or credentials are stored in production code.
