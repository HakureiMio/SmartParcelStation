from __future__ import annotations

from loguru import logger

from gateway.services.server_client import ServerClient


class HeartbeatService:
    def __init__(self, client: ServerClient):
        self.client = client

    def send_once(self) -> dict:
        data = self.client.heartbeat()
        logger.info("heartbeat sent: {}", data)
        return data
