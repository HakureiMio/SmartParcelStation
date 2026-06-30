"""
Network / hotspot management abstraction for gateway provisioning.

Supports:
- Linux (nmcli-based hotspot via linux_hotspot.py)
- Windows (returns unsupported_platform)
"""

from gateway.network.hotspot import HotspotManager, HotspotStatus, get_hotspot_manager

__all__ = ["HotspotManager", "HotspotStatus", "get_hotspot_manager"]
