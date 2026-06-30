"""
DEPRECATED: Mock BLE service has been moved to gateway/legacy/mock_ble_service.py.

Importing this module in production code will raise an ImportError.
Use RealBleCommandService from gateway.services.ble.adapter for production.
For tests, use pytest fixtures or fake classes.
"""

raise ImportError(
    "MockBleService has been removed from the production code path. "
    "Use RealBleCommandService from gateway.services.ble.adapter. "
    "The legacy mock implementation is available at gateway.legacy.mock_ble_service "
    "for historical reference and testing only."
)
