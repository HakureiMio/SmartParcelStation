"""
Legacy mock NFC service (moved from gateway/services/mock_nfc_service.py).

This file is retained for historical reference and testing only.
It is NOT imported by any production code path.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.models.entities import (
    CredentialStatus,
    CredentialType,
    LocalNfcCredential,
    LocalParcel,
    LocalParcelTagBinding,
    ParcelStatus,
    PickupEventType,
    TaskTargetType,
    TaskType,
)
from gateway.legacy.mock_ble_service import MockBleService
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


class MockNfcService:
    def __init__(self, db: Session, sync_service: SyncService, task_service: TaskService, ble_service: MockBleService):
        self.db = db
        self.sync_service = sync_service
        self.task_service = task_service
        self.ble = ble_service

    def handle_card(self, card_uid: str) -> dict:
        credential = self.db.scalar(select(LocalNfcCredential).where(
            LocalNfcCredential.credential_type == CredentialType.CARD_UID,
            LocalNfcCredential.credential_value == card_uid,
            LocalNfcCredential.status == CredentialStatus.ACTIVE,
        ))
        if not credential:
            event = self.sync_service.create_pickup_event(PickupEventType.NFC_ACCESS, {"card_uid": card_uid, "allowed": False})
            return {"ok": False, "reason": "credential_not_found", "event_id": event.event_id}

        parcel = self.db.scalar(select(LocalParcel).where(
            LocalParcel.receiver_user_id == credential.user_id,
            LocalParcel.status == ParcelStatus.WAITING_PICKUP,
        ))
        if not parcel:
            event = self.sync_service.create_pickup_event(PickupEventType.NFC_ACCESS, {"card_uid": card_uid, "allowed": False, "reason": "no_waiting_parcel"}, user_id=credential.user_id)
            return {"ok": False, "reason": "no_waiting_parcel", "event_id": event.event_id}

        binding = self.db.scalar(select(LocalParcelTagBinding).where(LocalParcelTagBinding.server_parcel_id == parcel.server_parcel_id))
        if not binding:
            event = self.sync_service.create_pickup_event(PickupEventType.NFC_ACCESS, {"card_uid": card_uid, "allowed": False, "reason": "binding_not_found"}, server_parcel_id=parcel.server_parcel_id, user_id=credential.user_id)
            return {"ok": False, "reason": "binding_not_found", "event_id": event.event_id}

        task = self.task_service.create_task(TaskType.TAG_WAKE, TaskTargetType.TAG, {"tag_id": binding.tag_id}, target_id=binding.tag_id)
        self.task_service.mark_running(task)
        result = self.ble.tag_wake(binding.tag_id)
        self.task_service.mark_done(task)

        event = self.sync_service.create_pickup_event(PickupEventType.TAG_WAKE, {"card_uid": card_uid, "task_id": task.task_id, "ble_result": result}, server_parcel_id=parcel.server_parcel_id, user_id=credential.user_id)
        return {"ok": True, "task_id": task.task_id, "event_id": event.event_id, "ble": result}
