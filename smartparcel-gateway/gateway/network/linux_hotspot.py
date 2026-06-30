"""
Linux hotspot manager using nmcli (NetworkManager command-line).

Requirements:
- nmcli must be installed (sudo apt install network-manager)
- Wi-Fi interface must support AP mode
- Root or appropriate NetworkManager permissions
- dnsmasq may be needed for DHCP (nmcli handles this automatically)

SSID format: SmartParcel-GW-XXXX (last 4 chars of device serial or device ID)
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from loguru import logger

from gateway.core.config import get_settings
from gateway.network.hotspot import HotspotManager, HotspotStatus


class LinuxHotspotManager(HotspotManager):
    """nmcli-based Wi-Fi hotspot management for Linux (Ubuntu/Debian/RPi OS)."""

    def __init__(self):
        self._settings = get_settings()
        self._con_name = "smartparcel-gw-ap"
        self._checked_nmcli: bool | None = None

    def _nmcli_available(self) -> bool:
        if self._checked_nmcli is None:
            self._checked_nmcli = Path("/usr/bin/nmcli").exists() or Path("/usr/sbin/nmcli").exists()
            if not self._checked_nmcli:
                # Also check via which
                try:
                    subprocess.run(["which", "nmcli"], capture_output=True, check=True)
                    self._checked_nmcli = True
                except Exception:
                    self._checked_nmcli = False
        return self._checked_nmcli

    def _ssid(self) -> str:
        suffix = (self._settings.gateway_serial or self._settings.gateway_device_id or "0000")[-4:]
        return f"{self._settings.wifi_ap_ssid_prefix}-{suffix}"

    def _password(self) -> str | None:
        pw = self._settings.wifi_ap_password
        if not pw:
            return None
        if len(pw) < 8:
            logger.warning("Wi-Fi AP password is shorter than 8 characters; WPA2 may reject it")
        return pw

    def _run(self, cmd: list[str], timeout: float = 15.0) -> tuple[int, str, str]:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except FileNotFoundError:
            return 127, "", "nmcli not found"
        except subprocess.TimeoutExpired:
            return 124, "", "command timed out"
        except Exception as exc:
            return 1, "", str(exc)

    def ensure_ap_started(self) -> HotspotStatus:
        if not self._nmcli_available():
            return HotspotStatus(
                active=False,
                error="nmcli_not_available: install network-manager package",
            )

        iface = self._settings.wifi_ap_interface
        ssid = self._ssid()
        password = self._password()
        ip = self._settings.wifi_ap_address

        # Check if the connection already exists
        rc, stdout, stderr = self._run(["nmcli", "-t", "-f", "NAME", "connection", "show"])
        existing = stdout.splitlines() if rc == 0 else []

        if self._con_name in existing:
            # Connection exists; check if active
            rc2, stdout2, _ = self._run(["nmcli", "-t", "-f", "GENERAL.STATE", "connection", "show", self._con_name])
            if rc2 == 0 and "activated" in stdout2.lower():
                logger.info("Hotspot {} already active on {}", ssid, iface)
                return HotspotStatus(
                    active=True,
                    ssid=ssid,
                    interface=iface,
                    ip_address=ip,
                )
            # Activate existing connection
            rc3, _, err3 = self._run(["nmcli", "connection", "up", self._con_name])
            if rc3 == 0:
                logger.info("Hotspot {} activated on {}", ssid, iface)
                return HotspotStatus(active=True, ssid=ssid, interface=iface, ip_address=ip)
            logger.warning("Failed to bring up existing hotspot connection: {}", err3)

        # Create new hotspot connection
        cmd = [
            "nmcli", "connection", "add",
            "type", "wifi",
            "con-name", self._con_name,
            "autoconnect", "yes",
            "ifname", iface,
            "mode", "ap",
            "ssid", ssid,
            "ipv4.method", "shared",
            "ipv4.addresses", f"{ip}/24",
        ]
        if password:
            cmd += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
        else:
            cmd += ["wifi-sec.key-mgmt", "none"]

        rc, stdout, stderr = self._run(cmd)
        if rc != 0:
            logger.error("nmcli connection add failed (rc={}): {}", rc, stderr)
            return HotspotStatus(
                active=False,
                ssid=ssid,
                interface=iface,
                error=f"nmcli_create_failed: {stderr}" if stderr else "nmcli_create_failed",
            )

        # Activate
        rc2, _, err2 = self._run(["nmcli", "connection", "up", self._con_name])
        if rc2 != 0:
            logger.error("nmcli connection up failed: {}", err2)
            return HotspotStatus(
                active=False,
                ssid=ssid,
                interface=iface,
                error=f"nmcli_activate_failed: {err2}" if err2 else "nmcli_activate_failed",
            )

        logger.info("Hotspot {} started on {} with IP {}", ssid, iface, ip)
        return HotspotStatus(active=True, ssid=ssid, interface=iface, ip_address=ip)

    def stop_ap(self) -> HotspotStatus:
        if not self._nmcli_available():
            return HotspotStatus(active=False, error="nmcli_not_available")

        ssid = self._ssid()
        rc, _, stderr = self._run(["nmcli", "connection", "down", self._con_name])
        if rc != 0:
            logger.warning("nmcli connection down failed: {}", stderr)
        return HotspotStatus(active=False, ssid=ssid)

    def status(self) -> HotspotStatus:
        if not self._nmcli_available():
            return HotspotStatus(active=False, error="nmcli_not_available")

        rc, stdout, _ = self._run(["nmcli", "-t", "-f", "GENERAL.STATE", "connection", "show", self._con_name])
        active = rc == 0 and "activated" in stdout.lower()
        return HotspotStatus(
            active=active,
            ssid=self._ssid() if active else None,
            interface=self._settings.wifi_ap_interface if active else None,
            ip_address=self._settings.wifi_ap_address if active else None,
        )
