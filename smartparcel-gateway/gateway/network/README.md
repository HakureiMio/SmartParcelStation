# Network / Hotspot Management

## Overview

The `gateway/network/` package provides platform-abstracted Wi-Fi hotspot management for gateway provisioning.

## Platform Support

| Platform | Implementation | Status |
|----------|---------------|--------|
| Linux    | `linux_hotspot.py` (nmcli) | ✅ Full support |
| Windows  | `windows_hotspot.py` | ❌ Returns `unsupported_platform` |
| macOS    | Not implemented | ❌ Returns `unsupported_platform` |

## Linux Hotspot (nmcli)

### Requirements

- `network-manager` package installed
- Wi-Fi adapter that supports AP (Access Point) mode
- Root or sudo permissions for creating hotspot connections
- `dnsmasq` (usually bundled with NetworkManager)

### How it works

1. Check if `nmcli` is available
2. Generate SSID: `SmartParcel-GW-XXXX` (last 4 chars of GATEWAY_SERIAL or GATEWAY_DEVICE_ID)
3. Create a `nmcli connection` of type `wifi` in `ap` mode with `ipv4.method=shared`
4. DHCP is handled automatically by NetworkManager's shared mode
5. Clients get IPs from the default dnsmasq range

### Permissions

The gateway process needs permission to create and activate NetworkManager connections.
Options:
- Run gateway as root (not recommended for production)
- Add gateway user to the `netdev` group
- Use a systemd service with `CAP_NET_ADMIN` capability
- Use polkit rules to allow the gateway user to manage connections

See `deploy/hotspot-permissions.md` for detailed setup instructions.

## Windows

Windows AP mode is not implemented. The prototype targets Linux-based gateway hardware
(Raspberry Pi, Ubuntu, Debian). A Windows implementation would require WinRT/Wi-Fi Direct
APIs which are outside the scope of this graduation project.

## Usage

```python
from gateway.network import get_hotspot_manager

hotspot = get_hotspot_manager()
status = hotspot.ensure_ap_started()
print(f"Hotspot active: {status.active}, SSID: {status.ssid}")
```
