"""
DEPRECATED: Mock NFC service has been moved to gateway/legacy/mock_nfc_service.py.

Importing this module in production code will raise an ImportError.
For tests, use pytest fixtures or fake classes.
"""

raise ImportError(
    "MockNfcService has been removed from the production code path. "
    "The legacy mock implementation is available at gateway.legacy.mock_nfc_service "
    "for historical reference and testing only."
)
