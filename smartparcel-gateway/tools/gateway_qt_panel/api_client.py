from __future__ import annotations

from typing import Any

import httpx

from app_config import LOCAL_API_BASE_URL


class ApiClient:
    def __init__(self, base_url: str = LOCAL_API_BASE_URL, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/local/health")

    def list_tags(self) -> dict[str, Any]:
        return self._request("GET", "/local/tags")

    def scan_tags(self, timeout_sec: float) -> dict[str, Any]:
        return self._request("POST", "/local/tags/scan", json={"timeout_sec": timeout_sec})

    def connect_tag(self, tag_id: str) -> dict[str, Any]:
        return self._request("POST", f"/local/tags/{tag_id}/connect")

    def wake_tag(self, tag_id: str, color: str, duration_sec: int) -> dict[str, Any]:
        return self._request("POST", f"/local/tags/{tag_id}/wake", json={"color": color, "duration_sec": duration_sec})

    def stop_tag(self, tag_id: str) -> dict[str, Any]:
        return self._request("POST", f"/local/tags/{tag_id}/stop")

    def read_tag_status(self, tag_id: str) -> dict[str, Any]:
        return self._request("GET", f"/local/tags/{tag_id}/status")


def server_health(server_base_url: str) -> dict[str, Any]:
    url = f"{server_base_url.rstrip('/')}/api/v1/health"
    with httpx.Client(timeout=8.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()
