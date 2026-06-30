# SmartParcel Gateway — Deployment Guide

## Quick Start

```bash
# 1. Install
cd smartparcel-gateway
bash deploy/install.sh

# 2. Edit .env with your device info
nano .env
# Set: GATEWAY_DEVICE_ID, GATEWAY_SERIAL, WIFI_AP_PASSWORD

# 3. Initialize database
python -m gateway.main init-db

# 4. Check status
python -m gateway.main status

# 5. Start in auto mode (unbound → provisioning, bound → runtime)
python -m gateway.main run

# Or start provisioning explicitly
python -m gateway.main provisioning
```

## Systemd Service

```bash
sudo cp deploy/smartparcel-gateway.service.example /etc/systemd/system/smartparcel-gateway.service
# Edit the paths in the service file
sudo nano /etc/systemd/system/smartparcel-gateway.service
sudo systemctl daemon-reload
sudo systemctl enable smartparcel-gateway
sudo systemctl start smartparcel-gateway
sudo journalctl -u smartparcel-gateway -f
```

## Files

| File | Purpose |
|------|---------|
| `install.sh` | One-time installation (venv, deps, db, .env) |
| `run-gateway.sh` | Simple launcher script |
| `smartparcel-gateway.service.example` | systemd unit file |
| `hotspot-permissions.md` | Linux permissions setup for Wi-Fi AP and Bluetooth |

## Requirements

- Python 3.10+
- Linux (Ubuntu 22.04+, Debian 12+, Raspberry Pi OS)
- NetworkManager (`nmcli`) for Wi-Fi hotspot
- Bluetooth adapter with BLE support
- `bleak` Python package for BLE GATT
