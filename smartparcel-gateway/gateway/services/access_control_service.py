from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.models.entities import (
    BindingStatus,
    CredentialStatus,
    CredentialType,
    EventSource,
    EventSyncStatus,
    GatewayTask,
    LocalNfcCredential,
    LocalParcel,
    LocalParcelTagBinding,
    LocalPickupEvent,
    LocalPickupSession,
    ParcelStatus,
    PickupEventType,
    PickupSessionStatus,
    TaskTargetType,
    TaskType,
)
from gateway.services.ble_service import BleService
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


COLOR_NAMES = {
    "BLUE": "蓝色",
    "GREEN": "绿色",
    "YELLOW": "黄色",
    "PURPLE": "紫色",
    "RED": "红色",
    "WHITE": "白色",
}
COLOR_POOL = tuple(COLOR_NAMES.keys())


class AccessControlService:
    def __init__(
        self,
        db: Session,
        sync_service: SyncService,
        task_service: TaskService,
        ble_service: BleService,
        station_id: str,
    ):
        self.db = db
        self.sync_service = sync_service
        self.task_service = task_service
        self.ble = ble_service
        self.station_id = str(station_id)

    def handle_access_card(
        self,
        reader_id: str,
        credential_type: str,
        credential_value: str,
    ) -> dict:
        credential_enum = self._normalize_credential_type(credential_type)
        if credential_enum is None:
            return self._deny(reader_id, credential_type, credential_value, "CREDENTIAL_NOT_FOUND", "未识别用户卡")

        credential = self.db.scalar(
            select(LocalNfcCredential).where(
                LocalNfcCredential.credential_type == credential_enum,
                LocalNfcCredential.credential_value == credential_value,
                LocalNfcCredential.status == CredentialStatus.ACTIVE,
                LocalNfcCredential.station_id == self.station_id,
            )
        )
        if credential is None:
            return self._deny(reader_id, credential_type, credential_value, "CREDENTIAL_NOT_FOUND", "未识别用户卡")

        parcels = list(
            self.db.scalars(
                select(LocalParcel).where(
                    LocalParcel.receiver_user_id == credential.user_id,
                    LocalParcel.station_id == self.station_id,
                    LocalParcel.status == ParcelStatus.WAITING_PICKUP,
                )
            )
        )
        if not parcels:
            return self._deny(
                reader_id,
                credential_type,
                credential_value,
                "NO_WAITING_PARCEL",
                "暂无待取包裹",
                user_id=credential.user_id,
            )

        session_id = f"sess_{uuid.uuid4().hex}"
        session_color = self._choose_session_color()
        color_display_name = COLOR_NAMES[session_color]
        shelves = [parcel.shelf_code or "未上架" for parcel in parcels]
        display_text = self._display_text(len(parcels), color_display_name, shelves)
        expires_at = datetime.utcnow() + timedelta(seconds=30)

        session = LocalPickupSession(
            session_id=session_id,
            user_id=credential.user_id,
            station_id=self.station_id,
            credential_type=credential_type,
            credential_value=credential_value,
            session_color=session_color,
            pickup_count=len(parcels),
            shelf_summary=" / ".join(shelves),
            display_text=display_text,
            status=PickupSessionStatus.ACTIVE,
            expires_at=expires_at,
        )
        self.db.add(session)
        self.db.commit()

        items: list[dict] = []
        warnings: list[str] = []
        wake_tasks: list[GatewayTask] = []
        now = datetime.utcnow()

        for parcel in parcels:
            binding = self.db.scalar(
                select(LocalParcelTagBinding).where(
                    LocalParcelTagBinding.server_parcel_id == parcel.server_parcel_id,
                    LocalParcelTagBinding.status == BindingStatus.ACTIVE,
                )
            )
            if binding is None:
                warnings.append(f"NO_ACTIVE_TAG_BINDING:{parcel.parcel_code}")
                items.append(
                    {
                        "parcel_code": parcel.parcel_code,
                        "shelf_code": parcel.shelf_code,
                        "tag_id": None,
                        "wake_result": "NO_ACTIVE_TAG_BINDING",
                    }
                )
                continue

            task_payload = {
                "pickup_session_id": session_id,
                "tag_id": binding.tag_id,
                "parcel_code": parcel.parcel_code,
                "shelf_code": parcel.shelf_code,
                "led_color": session_color,
                "blink_pattern": "SLOW",
                "beep_pattern": "SHORT_INTERVAL",
                "duration_sec": 30,
            }
            task = self.task_service.create_task(TaskType.TAG_WAKE, TaskTargetType.TAG, task_payload, target_id=binding.tag_id)
            wake_tasks.append(task)
            self.task_service.mark_running(task)
            try:
                ble_result = self.ble.tag_wake(
                    binding.tag_id,
                    led_color=session_color,
                    blink_pattern="SLOW",
                    beep_pattern="SHORT_INTERVAL",
                    duration_sec=30,
                    pickup_session_id=session_id,
                )
                if ble_result.get("result") == "OK":
                    self.task_service.mark_done(task)
                    wake_result = "OK"
                else:
                    self.task_service.mark_failed(task, json.dumps(ble_result, ensure_ascii=False))
                    wake_result = "FAILED"
                    warnings.append(f"TAG_WAKE_FAILED:{binding.tag_id}")
            except Exception as exc:
                self.task_service.mark_failed(task, str(exc))
                ble_result = {"tag_id": binding.tag_id, "result": "FAILED", "error": str(exc)}
                wake_result = "FAILED"
                warnings.append(f"TAG_WAKE_FAILED:{binding.tag_id}")

            binding.last_wake_session_id = session_id
            binding.last_wake_color = session_color
            binding.last_wake_at = now
            items.append(
                {
                    "parcel_code": parcel.parcel_code,
                    "shelf_code": parcel.shelf_code,
                    "tag_id": binding.tag_id,
                    "wake_result": wake_result,
                    "ble_result": ble_result,
                }
            )

        if not wake_tasks:
            warnings.append("NO_ACTIVE_TAG_BINDING")
            display_text = f"待取{len(parcels)}件｜请按货架号取件｜{' '.join(shelves)}"
            session.display_text = display_text

        payload = {
            "allowed": True,
            "reader_id": reader_id,
            "credential_type": credential_type,
            "credential_hash": self._credential_hash(credential_value),
            "pickup_session_id": session_id,
            "pickup_count": len(parcels),
            "session_color": session_color,
            "shelves": shelves,
            "items": [
                {key: value for key, value in item.items() if key != "ble_result"}
                for item in items
            ],
            "warnings": warnings,
        }
        self._record_local_pickup_event(PickupEventType.NFC_ACCESS, payload, user_id=credential.user_id)
        self._enqueue_audit("NFC_ACCESS_GRANTED", payload)
        if wake_tasks:
            self._enqueue_audit(
                "TAG_WAKE_STARTED",
                {
                    "reader_id": reader_id,
                    "pickup_session_id": session_id,
                    "session_color": session_color,
                    "tag_refs": [item["tag_id"] for item in items if item.get("tag_id")],
                    "shelves": shelves,
                    "pickup_count": len(parcels),
                },
            )
        self.db.commit()

        return {
            "access": "GRANTED",
            "reader_id": reader_id,
            "user_id": credential.user_id,
            "pickup_session_id": session_id,
            "pickup_count": len(parcels),
            "session_color": session_color,
            "color_display_name": color_display_name,
            "blink_pattern": "SLOW",
            "shelves": shelves,
            "display_text": display_text,
            "items": items,
            "warnings": warnings,
        }

    def _deny(
        self,
        reader_id: str,
        credential_type: str,
        credential_value: str,
        reason: str,
        display_text: str,
        user_id: str | None = None,
    ) -> dict:
        payload = {
            "allowed": False,
            "reader_id": reader_id,
            "credential_type": credential_type,
            "credential_hash": self._credential_hash(credential_value),
            "reason": reason,
            "display_text": display_text,
        }
        self._record_local_pickup_event(PickupEventType.NFC_ACCESS, payload, user_id=user_id)
        self._enqueue_audit("NFC_ACCESS_DENIED", payload)
        self.db.commit()
        return {
            "access": "DENIED",
            "reader_id": reader_id,
            "reason": reason,
            "display_text": display_text,
        }

    def _record_local_pickup_event(self, event_type: PickupEventType, payload: dict, user_id: str | None = None) -> None:
        self.db.add(
            LocalPickupEvent(
                event_id=uuid.uuid4().hex,
                user_id=user_id,
                station_id=self.station_id,
                event_type=event_type,
                source=EventSource.GATEWAY,
                payload_json=json.dumps(payload, ensure_ascii=True),
                sync_status=EventSyncStatus.LOCAL_ONLY,
            )
        )

    def _enqueue_audit(self, event_type: str, payload: dict) -> None:
        self.sync_service.enqueue_event_upload(
            {
                "event_id": uuid.uuid4().hex,
                "event_type": event_type,
                "payload_json": {
                    "station_id": self.station_id,
                    **payload,
                },
            }
        )

    def _choose_session_color(self) -> str:
        active_sessions = list(
            self.db.scalars(select(LocalPickupSession).where(LocalPickupSession.status == PickupSessionStatus.ACTIVE))
        )
        return COLOR_POOL[len(active_sessions) % len(COLOR_POOL)]

    @staticmethod
    def _display_text(pickup_count: int, color_display_name: str, shelves: list[str]) -> str:
        return f"待取{pickup_count}件｜{color_display_name}闪烁｜{' '.join(shelves)}"

    @staticmethod
    def _credential_hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_credential_type(value: str) -> CredentialType | None:
        try:
            return CredentialType(value.upper())
        except ValueError:
            return None
