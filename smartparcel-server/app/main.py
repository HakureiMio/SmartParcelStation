from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.mqtt import mqtt_manager

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # TODO: replace with production-grade MQTT connection retry strategy
    await mqtt_manager.start()
    yield
    await mqtt_manager.stop()


app = FastAPI(title=settings.app_name, version=settings.app_version, debug=settings.debug, lifespan=lifespan)
app.include_router(v1_router, prefix=settings.api_prefix)
