from __future__ import annotations

from sqlalchemy.orm import Session

from gateway.models.entities import TaskTargetType, TaskType
from gateway.services.mock_ble_service import MockBleService
from gateway.services.task_service import TaskService


def handle_server_command(db: Session, payload: dict, ble: MockBleService) -> dict:
    task_service = TaskService(db)
    cmd_type = payload.get("task_type", "SERVER_COMMAND")

    if cmd_type == TaskType.TAG_WAKE.value:
        tag_id = payload.get("target_id")
        task = task_service.create_task(TaskType.TAG_WAKE, TaskTargetType.TAG, payload, target_id=tag_id)
        task_service.mark_running(task)
        ble_result = ble.tag_wake(tag_id)
        task_service.mark_done(task)
        return {"task_id": task.task_id, "ble_result": ble_result}

    task = task_service.create_task(TaskType.SERVER_COMMAND, TaskTargetType.SERVER, payload)
    task_service.mark_done(task)
    return {"task_id": task.task_id}
