from __future__ import annotations

from typing import Any
from pydantic import BaseModel


class GatewayCommand(BaseModel):
    task_type: str
    target_id: str | None = None
    payload: dict[str, Any] = {}


class SyncPullResponse(BaseModel):
    parcels: list[dict[str, Any]] = []
    tags: list[dict[str, Any]] = []
    bindings: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    ack_ids: list[str] = []
