from __future__ import annotations

import json
import uuid
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.models.entities import (
    BindingStatus,
    EventSource,
    EventSyncStatus,
    LocalParcel,
    LocalParcelTagBinding,
    LocalPickupEvent,
    LocalTag,
    PickupEventType,
    SyncDirection,
    SyncQueue,
    SyncQueueStatus,
    TagStatus,
)
from gateway.services.server_client import ServerClient


class SyncService:
    def __init__(self, db: Session, client: ServerClient, station_id: str):
        self.db = db
        self.client = client
        self.station_id = station_id

    def sync_pull_once(self) -> dict:
        data = self.client.sync_pull()
        # Compatible with the server's current sync contract: {"events": [...]}
        # while keeping backward compatibility with the old denormalized payload.
        if "events" in data and not any(k in data for k in ("parcels", "tags", "bindings")):
            self.db.commit()
            logger.info("sync pull done")
            return data

        for p in data.get("parcels", []):
            obj = self.db.scalar(select(LocalParcel).where(LocalParcel.server_parcel_id == p["server_parcel_id"]))
            if obj is None:
                obj = LocalParcel(
                    server_parcel_id=p["server_parcel_id"],
                    parcel_code=p["parcel_code"],
                    pickup_code=p.get("pickup_code"),
                    receiver_user_id=p.get("receiver_user_id"),
                    receiver_phone=p.get("receiver_phone"),
                    station_id=p.get("station_id", self.station_id),
                    status=p.get("status", "CREATED"),
                )
                self.db.add(obj)
            else:
                obj.status = p.get("status", obj.status)
                obj.pickup_code = p.get("pickup_code")
                obj.receiver_user_id = p.get("receiver_user_id")
                obj.receiver_phone = p.get("receiver_phone")
                obj.local_updated_at = datetime.utcnow()
        for t in data.get("tags", []):
            obj = self.db.scalar(select(LocalTag).where(LocalTag.tag_id == t["tag_id"]))
            if obj is None:
                self.db.add(LocalTag(
                    server_tag_id=t.get("server_tag_id"),
                    tag_id=t["tag_id"],
                    encrypted_token=t.get("encrypted_token", ""),
                    station_id=t.get("station_id", self.station_id),
                    status=t.get("status", TagStatus.IDLE),
                ))
            else:
                obj.status = t.get("status", obj.status)
                obj.battery_level = t.get("battery_level")
                obj.last_seen_at = datetime.utcnow()
        for b in data.get("bindings", []):
            obj = self.db.scalar(select(LocalParcelTagBinding).where(LocalParcelTagBinding.pickup_binding_id == b["pickup_binding_id"]))
            if obj is None:
                self.db.add(LocalParcelTagBinding(
                    server_binding_id=b.get("server_binding_id"),
                    pickup_binding_id=b["pickup_binding_id"],
                    server_parcel_id=b["server_parcel_id"],
                    tag_id=b["tag_id"],
                    station_id=b.get("station_id", self.station_id),
                    status=b.get("status", BindingStatus.ACTIVE),
                ))
            else:
                obj.status = b.get("status", obj.status)
        self.db.commit()
        logger.info("sync pull done")
        return data

    def enqueue_event_upload(self, payload: dict) -> SyncQueue:
        row = SyncQueue(
            event_id=payload.get("event_id", uuid.uuid4().hex),
            direction=SyncDirection.UPLOAD,
            payload_json=json.dumps(payload, ensure_ascii=True),
            status=SyncQueueStatus.PENDING,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def sync_push_once(self) -> int:
        rows = list(self.db.scalars(select(SyncQueue).where(SyncQueue.direction == SyncDirection.UPLOAD, SyncQueue.status.in_([SyncQueueStatus.PENDING, SyncQueueStatus.FAILED]))))
        sent = 0
        for row in rows:
            try:
                payload = json.loads(row.payload_json)
                self.client.sync_push([payload])
                row.status = SyncQueueStatus.ACKED
                sent += 1
                event = self.db.scalar(select(LocalPickupEvent).where(LocalPickupEvent.event_id == row.event_id))
                if event:
                    event.sync_status = EventSyncStatus.UPLOADED
            except Exception:
                row.status = SyncQueueStatus.FAILED
                row.retry_count += 1
        self.db.commit()
        return sent

    def create_pickup_event(self, event_type: PickupEventType, payload: dict, server_parcel_id: str | None = None, user_id: str | None = None) -> LocalPickupEvent:
        event_id = uuid.uuid4().hex
        event = LocalPickupEvent(
            event_id=event_id,
            server_parcel_id=server_parcel_id,
            user_id=user_id,
            station_id=self.station_id,
            event_type=event_type,
            source=EventSource.GATEWAY,
            payload_json=json.dumps(payload, ensure_ascii=True),
            sync_status=EventSyncStatus.PENDING_UPLOAD,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        self.enqueue_event_upload({"event_id": event_id, "event_type": event_type.value, "payload_json": payload})
        return event
