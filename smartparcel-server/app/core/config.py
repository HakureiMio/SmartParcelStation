from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'smartparcel-server'
    app_version: str = '0.1.0'
    api_prefix: str = '/api/v1'
    debug: bool = True

    database_url: str = 'mysql+aiomysql://smartparcel:smartparcel@127.0.0.1:3306/smartparcel'

    dev_auth_enabled: bool = True
    default_gateway_secret: str = 'dev-gateway-secret'

    mqtt_enabled: bool = True
    mqtt_host: str = '127.0.0.1'
    mqtt_port: int = 1883
    mqtt_username: str = ''
    mqtt_password: str = ''
    mqtt_client_id: str = 'smartparcel-server'
    mqtt_keepalive: int = 60
    mqtt_topic_command_template: str = 'server/{gateway_code}/commands'
    mqtt_topic_event_template: str = 'gateway/{gateway_code}/events'
    mqtt_topic_status_template: str = 'gateway/{gateway_code}/status'
    mqtt_subscribe_all: bool = True

    @field_validator('debug', mode='before')
    @classmethod
    def parse_debug_bool(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {'1', 'true', 'yes', 'on', 'dev', 'debug'}:
                return True
            if normalized in {'0', 'false', 'no', 'off', 'prod', 'production', 'release'}:
                return False
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
