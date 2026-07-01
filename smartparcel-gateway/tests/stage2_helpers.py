from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gateway.db.base import Base
from gateway.services.access_control_service import AccessControlService
from gateway.services.ble_service import BleService
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


class Client:
    def __init__(self, events=None):
        self.events = events or []
        self.settings = SimpleNamespace(gateway_code="GW001")
    def sync_pull(self): return {"events": self.events}
    def sync_push(self, payload): return {"ok": True}


class Ble(BleService):
    def tag_wake(self, tag_id, **kwargs): return {"result": "OK", "tag_id": tag_id, **kwargs}
    def tag_stop(self, tag_id, pickup_session_id=None): return {"result": "OK"}
    def tag_status_query(self, tag_id): return {"result": "OK"}


def database():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, Session(engine)


def access_service(db):
    sync = SyncService(db, Client(), "1")
    return AccessControlService(db, sync, TaskService(db), Ble(), "1", gateway_code="GW001")
