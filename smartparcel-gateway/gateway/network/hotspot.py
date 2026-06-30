"""
Hotspot manager abstraction.

Defines the HotspotManager interface and a factory function that returns
the appropriate platform implementation.
"""

from __future__ import annotations

import platform
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HotspotStatus:
    active: bool
    ssid: str | None = None
    interface: str | None = None
    ip_address: str | None = None
    client_count: int = 0
    error: str | None = None
    platform: str = field(default_factory=platform.system)


class HotspotManager(ABC):
    """Platform-specific hotspot lifecycle management."""

    @abstractmethod
    def ensure_ap_started(self) -> HotspotStatus:
        """Start the Wi-Fi hotspot if not already running."""

    @abstractmethod
    def stop_ap(self) -> HotspotStatus:
        """Stop the Wi-Fi hotspot."""

    @abstractmethod
    def status(self) -> HotspotStatus:
        """Return current hotspot status."""


def get_hotspot_manager() -> HotspotManager:
    """Factory: return the appropriate HotspotManager for the current platform."""
    system = platform.system().lower()
    if system == "linux":
        from gateway.network.linux_hotspot import LinuxHotspotManager
        return LinuxHotspotManager()
    elif system == "windows":
        from gateway.network.windows_hotspot import WindowsHotspotManager
        return WindowsHotspotManager()
    else:
        from gateway.network.windows_hotspot import WindowsHotspotManager
        return WindowsHotspotManager()
