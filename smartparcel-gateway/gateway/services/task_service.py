from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gateway.models.entities import GatewayTask, TaskStatus, TaskTargetType, TaskType


class TaskService:
    def __init__(self, db: Session):
        self.db = db

    def create_task(self, task_type: TaskType, target_type: TaskTargetType, payload: dict, target_id: str | None = None, priority: int = 100) -> GatewayTask:
        task = GatewayTask(
            task_id=uuid.uuid4().hex,
            task_type=task_type,
            target_type=target_type,
            target_id=target_id,
            payload_json=json.dumps(payload, ensure_ascii=True),
            priority=priority,
            status=TaskStatus.PENDING,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def mark_running(self, task: GatewayTask) -> None:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        self.db.commit()

    def mark_done(self, task: GatewayTask) -> None:
        task.status = TaskStatus.DONE
        task.finished_at = datetime.utcnow()
        self.db.commit()

    def mark_failed(self, task: GatewayTask, message: str) -> None:
        task.status = TaskStatus.FAILED
        task.error_message = message
        task.retry_count += 1
        task.finished_at = datetime.utcnow()
        self.db.commit()

    def list_tasks(self, limit: int = 50) -> list[GatewayTask]:
        stmt = select(GatewayTask).order_by(GatewayTask.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))
