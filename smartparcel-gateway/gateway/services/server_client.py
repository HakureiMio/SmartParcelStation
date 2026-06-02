from __future__ import annotations

from typing import Any
import httpx

from gateway.core.config import Settings
from gateway.core.security import build_gateway_headers, serialize_json_body


class ServerClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.server_base_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict[str, Any] | list[Any] | None = None):
        headers = build_gateway_headers(
            secret=self.settings.gateway_secret,
            gateway_code=self.settings.gateway_code,
            method=method,
            path=path,
            payload=payload,
        )
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=15.0, trust_env=False) as client:
            if method.upper() == "GET":
                resp = client.get(url, headers=headers)
            else:
                resp = client.request(method, url, headers=headers, content=serialize_json_body(payload))
            resp.raise_for_status()
            if not resp.content:
                return {}
            return resp.json()

    def health(self):
        return self._request("GET", "/api/v1/health")

    def heartbeat(self):
        return self._request("POST", "/api/v1/gateways/heartbeat", {"gateway_code": self.settings.gateway_code, "status": "ONLINE"})

    def sync_pull(self):
        return self._request("GET", f"/api/v1/gateways/{self.settings.gateway_code}/sync/pull")

    def sync_push(self, payload: list[dict[str, Any]]):
        return self._request("POST", f"/api/v1/gateways/{self.settings.gateway_code}/sync/push", payload)

    def post_events(self, payload: dict[str, Any]):
        return self._request("POST", f"/api/v1/gateways/{self.settings.gateway_code}/events", payload)

    def report_tag_status(self, payload: dict[str, Any]):
        return self._request("POST", "/api/v1/tags/status-report", payload)

    def pickup_confirm(self, payload: dict[str, Any]):
        return self._request("POST", "/api/v1/pickup/confirm", payload)
