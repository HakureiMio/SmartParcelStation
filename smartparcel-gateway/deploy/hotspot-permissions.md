# Hotspot Permissions Setup

The gateway's provisioning mode uses NetworkManager (`nmcli`) to create a Wi-Fi
hotspot. This requires specific permissions.

## Option 1: Run gateway as a user with NetworkManager permissions

Add the gateway user to the `netdev` group:

```bash
sudo usermod -a -G netdev smartparcel
```

Then create a polkit rule to allow the user to manage connections:

```bash
sudo tee /etc/polkit-1/localauthority/50-local.d/50-smartparcel-gateway.pkla << 'EOF'
[SmartParcel Gateway NetworkManager Control]
Identity=unix-user:smartparcel
Action=org.freedesktop.NetworkManager.*
ResultAny=yes
ResultInactive=yes
ResultActive=yes
EOF
```

## Option 2: Use systemd service with capabilities

Add `AmbientCapabilities=CAP_NET_ADMIN` to the systemd service file and ensure
the user has access to the D-Bus system bus.

## Option 3: Pre-create the hotspot connection as root

Create the hotspot connection once as root, then the gateway only needs to
bring it up/down:

```bash
# Generate the SSID (replace XXXX with last 4 chars of your device serial)
sudo nmcli connection add \
    type wifi \
    con-name smartparcel-gw-ap \
    autoconnect no \
    ifname wlan0 \
    mode ap \
    ssid SmartParcel-GW-XXXX \
    ipv4.method shared \
    ipv4.addresses 192.168.4.1/24 \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk YOUR_SECURE_PASSWORD
```

Then set the connection name in the gateway config (default: `smartparcel-gw-ap`).

## Bluetooth (BLE) permissions

The gateway user needs access to the Bluetooth adapter:

```bash
sudo usermod -a -G bluetooth smartparcel
```

On some systems, you may also need to grant D-Bus access for BlueZ:

```bash
sudo tee /etc/polkit-1/localauthority/50-local.d/50-smartparcel-bluetooth.pkla << 'EOF'
[SmartParcel Gateway Bluetooth Control]
Identity=unix-user:smartparcel
Action=org.bluez.*
ResultAny=yes
ResultInactive=yes
ResultActive=yes
EOF
```

## Security Notes

These permission grants are permissive. For production deployments:
- Restrict polkit rules to specific actions
- Use a dedicated gateway user
- Consider running Bluetooth and NetworkManager operations via a small
  privileged helper daemon instead of granting broad permissions
