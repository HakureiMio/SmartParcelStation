from __future__ import annotations

import re
from datetime import datetime

from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select

from gateway.core.config import get_settings
from gateway.db.session import SessionLocal
from gateway.models.entities import LocalTag
from gateway.models.entities import TagStatus
from gateway.services.access_control_service import AccessControlService
from gateway.services.ble import get_ble_tag_service
from gateway.services.mock_ble_service import MockBleService
from gateway.services.server_client import ServerClient
from gateway.services.sync_service import SyncService
from gateway.services.task_service import TaskService


app = FastAPI(title="SmartParcel Gateway Local API")
FACTORY_BLE_NAME_RE = re.compile(r"^SPS-[A-Z0-9]{2,8}-[0-9]{8}-[0-9]{4,8}$")
LEGACY_BLE_NAME_RE = re.compile(r"^SPS-TAG-[0-9A-Fa-f]{4,8}$")


class GateAccessIn(BaseModel):
    reader_id: str
    credential_type: str = "CARD_UID"
    credential_value: str


class ScanTagsIn(BaseModel):
    timeout_sec: float = 5.0


class RegisterFromBleIn(BaseModel):
    ble_name: str
    ble_address: str


class WakeTagIn(BaseModel):
    color: str = "BLUE"
    duration_sec: int = 30


def _now() -> datetime:
    return datetime.utcnow()


def _is_valid_ble_name(ble_name: str) -> bool:
    return bool(FACTORY_BLE_NAME_RE.match(ble_name) or LEGACY_BLE_NAME_RE.match(ble_name))


def _next_local_no(db) -> int:
    current = db.scalar(select(func.max(LocalTag.local_no))) or 0
    return int(current) + 1


def _tag_status_value(tag: LocalTag) -> str:
    status = tag.status
    return status.value if hasattr(status, "value") else str(status)


def _tag_summary(tag: LocalTag) -> dict:
    return {
        "tag_id": tag.tag_id,
        "display_name": tag.display_name,
        "local_no": tag.local_no,
        "status": _tag_status_value(tag),
        "battery_mv": tag.battery_mv,
        "battery_level": tag.battery_level,
        "last_seen_at": tag.last_seen_at.isoformat() if tag.last_seen_at else None,
        "ble_name": tag.ble_name,
        "ble_address": tag.ble_address,
    }


def _tag_detail(tag: LocalTag) -> dict:
    data = _tag_summary(tag)
    data.update(
        {
            "tag_uid": tag.tag_uid,
            "registered_at": tag.registered_at.isoformat() if tag.registered_at else None,
            "last_connected_at": tag.last_connected_at.isoformat() if tag.last_connected_at else None,
            "hw_model": tag.hw_model,
            "fw_version": tag.fw_version,
        }
    )
    return data


def _find_tag(db, tag_id: str) -> LocalTag:
    tag = db.scalar(select(LocalTag).where(LocalTag.tag_id == tag_id))
    if tag is None:
        raise HTTPException(status_code=404, detail=f"tag not found: {tag_id}")
    return tag


def _require_ble_address(tag: LocalTag) -> str:
    if not tag.ble_address:
        raise HTTPException(status_code=400, detail="tag has no ble_address")
    return tag.ble_address


def _apply_ble_result(tag: LocalTag, result: dict, success_status: TagStatus | None = None) -> None:
    if result.get("ok"):
        if success_status is not None:
            tag.status = success_status
        tag.last_seen_at = _now()
        if "battery_mv" in result:
            tag.battery_mv = result.get("battery_mv")
        if "battery_level" in result:
            tag.battery_level = result.get("battery_level")
        return

    tag.status = TagStatus.ERROR
    tag.last_error_type = result.get("error") or "ble_error"
    tag.last_error_message = result.get("message")
    tag.last_error_at = _now()


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


@app.post("/local/tags/scan")
async def scan_tags(payload: ScanTagsIn):
    db = SessionLocal()
    try:
        items = await get_ble_tag_service().scan_tags(payload.timeout_sec)
        merged = []
        now = _now()
        for item in items:
            ble_name = item.get("ble_name")
            ble_address = item.get("ble_address")
            if item.get("ok") is False:
                merged.append(item)
                continue

            tag = None
            if ble_name or ble_address:
                tag = db.scalar(
                    select(LocalTag).where(
                        or_(
                            LocalTag.ble_name == ble_name,
                            LocalTag.tag_uid == ble_name,
                            LocalTag.ble_address == ble_address,
                        )
                    )
                )
            data = dict(item)
            if tag:
                tag.last_seen_at = now
                tag.ble_address = ble_address or tag.ble_address
                data.update(
                    {
                        "registered": True,
                        "tag_id": tag.tag_id,
                        "local_no": tag.local_no,
                        "display_name": tag.display_name,
                        "status": _tag_status_value(tag),
                        "last_seen_at": tag.last_seen_at.isoformat(),
                    }
                )
            else:
                data.update({"registered": False, "local_no": None, "display_name": None})
            merged.append(data)
        db.commit()
        return {"ok": True, "items": merged}
    finally:
        db.close()


@app.post("/local/tags/register-from-ble")
def register_from_ble(payload: RegisterFromBleIn):
    ble_name = payload.ble_name.strip()
    ble_address = payload.ble_address.strip()
    if not _is_valid_ble_name(ble_name):
        raise HTTPException(status_code=400, detail="invalid ble_name")

    db = SessionLocal()
    try:
        now = _now()
        tag = db.scalar(
            select(LocalTag).where(
                or_(
                    LocalTag.ble_name == ble_name,
                    LocalTag.tag_uid == ble_name,
                    LocalTag.tag_id == ble_name,
                )
            )
        )
        if tag is None:
            local_no = _next_local_no(db)
            tag = LocalTag(
                tag_id=f"SPS-TAG-{local_no:04d}",
                tag_uid=ble_name,
                ble_name=ble_name,
                ble_address=ble_address,
                local_no=local_no,
                display_name=f"标签 {local_no:03d}",
                encrypted_token="",
                station_id=str(get_settings().station_id),
                status=TagStatus.ONLINE,
                registered_at=now,
                last_seen_at=now,
            )
            db.add(tag)
        else:
            tag.tag_uid = tag.tag_uid or ble_name
            tag.ble_name = tag.ble_name or ble_name
            tag.ble_address = ble_address
            tag.local_no = tag.local_no or _next_local_no(db)
            tag.display_name = tag.display_name or f"标签 {tag.local_no:03d}"
            tag.registered_at = tag.registered_at or now
            tag.last_seen_at = now
            tag.status = TagStatus.ONLINE
        db.commit()
        db.refresh(tag)
        return {"ok": True, "item": _tag_detail(tag)}
    finally:
        db.close()


@app.get("/local/tags")
def list_tags():
    db = SessionLocal()
    try:
        items = list(db.scalars(select(LocalTag).order_by(LocalTag.local_no.asc(), LocalTag.created_at.desc())))
        return {"ok": True, "items": [_tag_summary(item) for item in items]}
    finally:
        db.close()


@app.get("/local/tags/{tag_id}")
def get_tag(tag_id: str):
    db = SessionLocal()
    try:
        return {"ok": True, "item": _tag_detail(_find_tag(db, tag_id))}
    finally:
        db.close()


@app.post("/local/tags/{tag_id}/connect")
async def connect_tag(tag_id: str):
    db = SessionLocal()
    try:
        tag = _find_tag(db, tag_id)
        result = await get_ble_tag_service().connect_tag(_require_ble_address(tag))
        if result.get("ok"):
            tag.status = TagStatus.ONLINE
            tag.last_connected_at = _now()
        else:
            _apply_ble_result(tag, result)
        db.commit()
        return {"ok": bool(result.get("ok")), "result": result, "item": _tag_detail(tag)}
    finally:
        db.close()


@app.post("/local/tags/{tag_id}/wake")
async def wake_tag(tag_id: str, payload: WakeTagIn):
    db = SessionLocal()
    try:
        tag = _find_tag(db, tag_id)
        result = await get_ble_tag_service().wake_tag(_require_ble_address(tag), payload.color, payload.duration_sec)
        _apply_ble_result(tag, result, TagStatus.RUNNING)
        db.commit()
        return {"ok": bool(result.get("ok")), "result": result, "item": _tag_detail(tag)}
    finally:
        db.close()


@app.post("/local/tags/{tag_id}/stop")
async def stop_tag(tag_id: str):
    db = SessionLocal()
    try:
        tag = _find_tag(db, tag_id)
        result = await get_ble_tag_service().stop_alert(_require_ble_address(tag))
        _apply_ble_result(tag, result, TagStatus.ONLINE)
        db.commit()
        return {"ok": bool(result.get("ok")), "result": result, "item": _tag_detail(tag)}
    finally:
        db.close()


@app.get("/local/tags/{tag_id}/status")
async def read_tag_status(tag_id: str):
    db = SessionLocal()
    try:
        tag = _find_tag(db, tag_id)
        result = await get_ble_tag_service().read_status(_require_ble_address(tag))
        _apply_ble_result(tag, result, TagStatus.ONLINE if result.get("ok") else None)
        db.commit()
        return {"ok": bool(result.get("ok")), "result": result, "item": _tag_detail(tag)}
    finally:
        db.close()
