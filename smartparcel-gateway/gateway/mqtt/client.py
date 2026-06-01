from __future__ import annotations

import json
import threading
import time
from typing import Callable

import paho.mqtt.client as mqtt
from loguru import logger


class GatewayMqttClient:
    def __init__(self, host: str, port: int, username: str, password: str, gateway_code: str, command_handler: Callable[[dict], None]):
        self.gateway_code = gateway_code
        self.command_topic = f"server/{gateway_code}/commands"
        self.status_topic = f"gateway/{gateway_code}/status"
        self.events_topic = f"gateway/{gateway_code}/events"
        self.command_handler = command_handler

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self.client.username_pw_set(username, password)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.connect_async(host, port, keepalive=60)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        logger.info("mqtt connected: {}", reason_code)
        client.subscribe(self.command_topic)
        self.publish_status({"status": "ONLINE", "gateway_code": self.gateway_code})

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            self.command_handler(payload)
        except Exception as ex:
            logger.exception("mqtt message handle failed: {}", ex)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        logger.warning("mqtt disconnected: {}", reason_code)

    def start(self):
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish_status(self, payload: dict):
        self.client.publish(self.status_topic, json.dumps(payload, ensure_ascii=True), qos=1)

    def publish_event(self, payload: dict):
        self.client.publish(self.events_topic, json.dumps(payload, ensure_ascii=True), qos=1)
