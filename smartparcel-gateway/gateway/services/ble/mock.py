"""
DEPRECATED: Mock BLE tag service has been moved to gateway/legacy/mock_ble_tag_service.py.

Importing this module in production code will raise an ImportError.
Use RealBleTagService (gateway.services.ble.real) for production.
For tests, use pytest fixtures or fake classes.
"""

raise ImportError(
    "MockBleTagService has been removed from the production code path. "
    "Use RealBleTagService from gateway.services.ble.real. "
    "The legacy mock implementation is available at gateway.legacy.mock_ble_tag_service "
    "for historical reference and testing only."
)
