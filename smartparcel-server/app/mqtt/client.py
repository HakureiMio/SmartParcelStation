import json
import logging

from gmqtt import Client as MQTTClient

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MQTTManager:
    def __init__(self) -> None:
        self.client: MQTTClient | None = None

    async def start(self) -> None:
        if not settings.mqtt_enabled:
            logger.info('MQTT disabled')
            return

        self.client = MQTTClient(settings.mqtt_client_id)
        if settings.mqtt_username:
            self.client.set_auth_credentials(settings.mqtt_username, settings.mqtt_password)

        self.client.on_message = self.on_message
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

        await self.client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=settings.mqtt_keepalive)
        logger.info('Connected to EMQX at %s:%s', settings.mqtt_host, settings.mqtt_port)

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()

    def on_connect(self, client, flags, rc, properties):
        logger.info('MQTT connected rc=%s', rc)
        if settings.mqtt_subscribe_all:
            client.subscribe('gateway/+/events')
            client.subscribe('gateway/+/status')

    def on_disconnect(self, client, packet, exc=None):
        logger.info('MQTT disconnected')

    def on_message(self, client, topic, payload, qos, properties):
        try:
            body = json.loads(payload.decode('utf-8'))
        except Exception:
            body = {'raw': payload.decode('utf-8', errors='ignore')}
        logger.info('MQTT message topic=%s body=%s', topic, body)
        return 0

    def publish_gateway_command(self, gateway_code: str, payload: dict) -> None:
        if not self.client:
            return
        topic = settings.mqtt_topic_command_template.format(gateway_code=gateway_code)
        self.client.publish(topic, json.dumps(payload), qos=1)


mqtt_manager = MQTTManager()
