from __future__ import annotations

import os
from typing import Any

import httpx


class ApiClient:
    def __init__(self, base_url: str | None = None, dev_user_id: int = 1, dev_role: str = 'SERVER_ADMIN'):
        self.base_url = (base_url or os.getenv('SERVER_BASE_URL') or os.getenv('API_BASE_URL') or 'http://127.0.0.1:18000').rstrip('/')
        self.api_base = f'{self.base_url}/api/v1'
        self.dev_headers = {'X-Dev-User-Id': str(dev_user_id), 'X-Dev-Role': dev_role}

    def request(self, method: str, path: str, payload: Any | None = None, auth: bool = False) -> Any:
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers.update(self.dev_headers)
        with httpx.Client(timeout=15.0, trust_env=False) as client:
            response = client.request(method, f'{self.api_base}{path}', json=payload, headers=headers)
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()

    def get(self, path: str) -> Any:
        return self.request('GET', path)

    def post(self, path: str, payload: Any | None = None, auth: bool = False) -> Any:
        return self.request('POST', path, payload, auth=auth)

    def patch(self, path: str, payload: Any, auth: bool = True) -> Any:
        return self.request('PATCH', path, payload, auth=auth)
