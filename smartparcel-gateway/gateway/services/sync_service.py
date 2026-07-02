from __future__ import annotations

import json
import uuid
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.models.entities import (
    BindingStatus,
    CredentialStatus,
    CredentialType,
    EventSource,
    EventSyncStatus,
    LocalParcel,
    LocalParcelTagBinding,
    LocalNfcCredential,
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
            for event in data.get("events", []):
                self.apply_sync_event(event.get("event_type", ""), event.get("payload_json") or {})
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
                    receiver_name_masked=p.get("receiver_name_masked"),
                    shelf_code=p.get("shelf_code") or p.get("shelf"),
                    station_id=p.get("station_id", self.station_id),
                    status=p.get("status", "CREATED"),
                    origin=p.get("origin", "SERVER_MANUAL"),
                    sync_status=p.get("sync_status", "SYNCED"),
                )
                self.db.add(obj)
            else:
                obj.status = p.get("status", obj.status)
                obj.pickup_code = p.get("pickup_code")
                obj.receiver_user_id = p.get("receiver_user_id")
                obj.receiver_phone = p.get("receiver_phone")
                obj.receiver_name_masked = p.get("receiver_name_masked")
                incoming_shelf = p.get("shelf_code") or p.get("shelf")
                if incoming_shelf is not None:
                    obj.shelf_code = incoming_shelf
                obj.origin = p.get("origin", obj.origin)
                obj.sync_status = p.get("sync_status", obj.sync_status)
                obj.local_updated_at = datetime.utcnow()
        if data.get("tags") or data.get("bindings"):
            logger.info("ignore server tag/binding payloads: smart tag master data is gateway-local-first")
        self.db.commit()
        logger.info("sync pull done")
        return data

    def apply_sync_event(self, event_type: str, payload: dict) -> None:
        kind = event_type.upper()
        now = datetime.utcnow()
        if kind == "USER_ACCESS_CREDENTIAL_UPSERT":
            value = payload["credential_value"]
            row = self.db.scalar(select(LocalNfcCredential).where(LocalNfcCredential.credential_value == value))
            status = CredentialStatus(payload.get("status", "ACTIVE"))
            if row is None:
                row = LocalNfcCredential(
                    server_credential_id=str(payload.get("id")) if payload.get("id") is not None else None,
                    credential_type=CredentialType(payload.get("credential_type", "CARD_UID")),
                    credential_value=value, user_id=str(payload["user_id"]),
                    station_id=str(payload.get("station_id", self.station_id)), status=status,
                    expires_at=self._parse_datetime(payload.get("expires_at")), last_synced_at=now,
                )
                self.db.add(row)
            else:
                # A terminal local card state is never resurrected by a stale UPSERT.
                if row.status in {CredentialStatus.LOST, CredentialStatus.REPLACED, CredentialStatus.DISABLED} and status == CredentialStatus.ACTIVE:
                    return
                row.user_id, row.station_id, row.status = str(payload["user_id"]), str(payload.get("station_id", self.station_id)), status
                row.expires_at, row.last_synced_at = self._parse_datetime(payload.get("expires_at")), now
            return
        if kind == "USER_ACCESS_CREDENTIAL_DISABLED":
            row = self.db.scalar(select(LocalNfcCredential).where(LocalNfcCredential.credential_value == payload["credential_value"]))
            if row:
                row.status = CredentialStatus(payload.get("status", "DISABLED"))
                row.reason, row.last_synced_at = payload.get("reason"), now
                if row.status == CredentialStatus.REPLACED: row.replaced_at = now
                elif row.status == CredentialStatus.LOST: row.lost_reported_at = now
                else: row.disabled_at = now
            return
        if kind == "USER_ACCESS_CREDENTIAL_REPLACED":
            old = payload.get("old_credential_value") or payload.get("credential_value")
            new = payload.get("new_credential_value")
            if old:
                self.apply_sync_event("USER_ACCESS_CREDENTIAL_DISABLED", {**payload, "credential_value": old, "status": "REPLACED"})
            if new:
                self.apply_sync_event("USER_ACCESS_CREDENTIAL_UPSERT", {**payload, "credential_value": new, "status": "ACTIVE"})
            self.enqueue_event_upload({"event_type": "GATE_CARD_REPLACED_APPLIED", "payload_json": {
                "old_credential_hash": self._hash(old), "new_credential_hash": self._hash(new), "station_id": self.station_id,
            }})
            return
        if kind == "PARCEL_UPSERT":
            parcel_id = str(payload.get("server_parcel_id") or payload.get("parcel_id"))
            row = self.db.scalar(select(LocalParcel).where(LocalParcel.server_parcel_id == parcel_id))
            if row is None:
                row = LocalParcel(server_parcel_id=parcel_id, parcel_code=payload["parcel_code"], station_id=str(payload.get("station_id", self.station_id)))
                self.db.add(row)
            for source, target in (("pickup_code", "pickup_code"), ("receiver_user_id", "receiver_user_id"), ("user_id", "receiver_user_id"), ("receiver_phone", "receiver_phone"), ("receiver_name_masked", "receiver_name_masked")):
                if payload.get(source) is not None: setattr(row, target, str(payload[source]))
            incoming_shelf = payload.get("shelf_code")
            if incoming_shelf is None:
                incoming_shelf = payload.get("shelf")
            if incoming_shelf is not None:
                row.shelf_code = str(incoming_shelf)
            row.status = payload.get("status", row.status); row.local_updated_at = now
            return
        if kind == "PARCEL_TAG_BINDING_UPSERT":
            parcel_id = str(payload.get("server_parcel_id") or payload.get("parcel_id"))
            binding_id = payload.get("pickup_binding_id") or f"sync-{parcel_id}-{payload['tag_id']}"
            row = self.db.scalar(select(LocalParcelTagBinding).where(LocalParcelTagBinding.pickup_binding_id == binding_id))
            if row is None:
                row = LocalParcelTagBinding(pickup_binding_id=binding_id, server_parcel_id=parcel_id, tag_id=payload["tag_id"], station_id=str(payload.get("station_id", self.station_id)))
                self.db.add(row)
            row.status = payload.get("status", "ACTIVE")
            tag = self.db.scalar(select(LocalTag).where(LocalTag.tag_id == payload["tag_id"]))
            if tag is None:
                tag = LocalTag(tag_id=payload["tag_id"], station_id=str(payload.get("station_id", self.station_id)), encrypted_token=payload.get("encrypted_token", ""))
                self.db.add(tag)
            elif payload.get("encrypted_token") is not None: tag.encrypted_token = payload["encrypted_token"]
            return
        if kind == "PARCEL_PICKUP_CONFIRMED":
            parcel_id = str(payload.get("server_parcel_id") or payload.get("parcel_id"))
            parcel = self.db.scalar(select(LocalParcel).where(LocalParcel.server_parcel_id == parcel_id))
            if parcel: parcel.status = "PICKED_UP"
            bindings = list(self.db.scalars(select(LocalParcelTagBinding).where(LocalParcelTagBinding.server_parcel_id == parcel_id)))
            for binding in bindings:
                if binding.status == BindingStatus.ACTIVE:
                    try:
                        from gateway.services.ble.adapter import RealBleCommandService
                        RealBleCommandService().tag_stop(binding.tag_id, binding.last_wake_session_id)
                    except Exception as exc:
                        logger.warning("failed to stop picked-up tag {}: {}", binding.tag_id, exc)
                binding.status, binding.released_at, binding.release_reason = BindingStatus.RELEASED, now, "SERVER_PICKUP_CONFIRMED"
                tag = self.db.scalar(select(LocalTag).where(LocalTag.tag_id == binding.tag_id))
                if tag: tag.status = TagStatus.IDLE
            return
        if kind == "GATE_USER_AUTH_REQUESTED":
            from gateway.services.access_control_service import AccessControlService
            from gateway.services.ble.adapter import RealBleCommandService
            from gateway.services.task_service import TaskService
            service = AccessControlService(
                self.db, self, TaskService(self.db), RealBleCommandService(), self.station_id,
                gateway_code=self.client.settings.gateway_code,
                auth_result_ttl_seconds=getattr(self.client.settings, "gate_auth_result_ttl_seconds", 15),
            )
            service.handle_gate_auth_by_user(payload["auth_method"], payload["reader_id"], str(payload["user_id"]), payload.get("request_id"), payload.get("session_id"))

    @staticmethod
    def _parse_datetime(value):
        if not value: return None
        if isinstance(value, datetime): return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)

    @staticmethod
    def _hash(value):
        import hashlib
        return hashlib.sha256(str(value or "").encode()).hexdigest()

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
