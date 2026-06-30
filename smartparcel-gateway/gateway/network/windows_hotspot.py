"""
Windows hotspot manager — NOT IMPLEMENTED.

Windows AP mode requires WinRT/Wi-Fi Direct APIs and is not supported
in the current prototype. Returns unsupported_platform error.
"""

from __future__ import annotations

from gateway.network.hotspot import HotspotManager, HotspotStatus


class WindowsHotspotManager(HotspotManager):
    """Stub: Windows hotspot management is not supported in this prototype.

    Use a Linux gateway (Ubuntu/Debian/Raspberry Pi OS) for production deployment.
    """

    def ensure_ap_started(self) -> HotspotStatus:
        return HotspotStatus(
            active=False,
            error="unsupported_platform: Windows AP mode is not implemented. Use a Linux gateway.",
        )

    def stop_ap(self) -> HotspotStatus:
        return HotspotStatus(
            active=False,
            error="unsupported_platform: Windows AP mode is not implemented.",
        )

    def status(self) -> HotspotStatus:
        return HotspotStatus(
            active=False,
            error="unsupported_platform",
        )
