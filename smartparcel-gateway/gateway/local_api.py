from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from gateway.core.config import get_settings
from gateway.db.session import SessionLocal
from gateway.services.access_control_service import AccessControlService
from gateway.services.mock_ble_service import MockBleService
from gateway.services.server_client import ServerClient
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


app = FastAPI(title="SmartParcel Gateway Local API")


class GateAccessIn(BaseModel):
    reader_id: str
    credential_type: str = "CARD_UID"
    credential_value: str


@app.get("/local/health")
def local_health():
    settings = get_settings()
    return {
        "status": "ok",
        "gateway_code": settings.gateway_code,
        "station_id": str(settings.station_id),
    }


@app.post("/local/gate/access-card")
def gate_access_card(payload: GateAccessIn):
    settings = get_settings()
    db = SessionLocal()
    try:
        service = AccessControlService(
            db,
            SyncService(db, ServerClient(settings), settings.station_id),
            TaskService(db),
            MockBleService(),
            settings.station_id,
        )
        return service.handle_access_card(
            reader_id=payload.reader_id,
            credential_type=payload.credential_type,
            credential_value=payload.credential_value,
        )
    finally:
        db.close()
