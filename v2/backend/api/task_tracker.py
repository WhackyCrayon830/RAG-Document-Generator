"""Task management utilities for async operations."""

import json
from datetime import datetime
from typing import Any, Optional
import redis

from backend.config.settings import get_settings
from backend.api.models import TaskStatus, TaskStatusResponse


class TaskTracker:
    """Track async task progress and results."""

    def __init__(self):
        settings = get_settings()
        # Extract host and port from redis_url
        # redis_url format: redis://localhost:6379/0
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self.prefix = "task:"

    def start_task(self, task_id: str, task_name: str, params: dict) -> None:
        """Record task start."""
        data = {
            "task_id": task_id,
            "task_name": task_name,
            "status": TaskStatus.STARTED.value,
            "started_at": datetime.utcnow().isoformat(),
            "params": json.dumps(params),
            "progress": 0,
            "current": "Initializing...",
        }
        self.redis_client.hset(self.prefix + task_id, mapping=data)

    def update_progress(self, task_id: str, progress: int, current: str, total_steps: int = 100) -> None:
        """Update task progress."""
        self.redis_client.hset(
            self.prefix + task_id,
            mapping={
                "progress": str(progress),
                "current": current,
                "total_steps": str(total_steps),
            },
        )

    def complete_task(self, task_id: str, result: dict) -> None:
        """Mark task as completed with result."""
        self.redis_client.hset(
            self.prefix + task_id,
            mapping={
                "status": TaskStatus.SUCCESS.value,
                "result": json.dumps(result),
                "progress": "100",
                "completed_at": datetime.utcnow().isoformat(),
            },
        )

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed with error."""
        self.redis_client.hset(
            self.prefix + task_id,
            mapping={
                "status": TaskStatus.FAILURE.value,
                "error": error,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )

    def get_status(self, task_id: str) -> Optional[TaskStatusResponse]:
        """Retrieve task status."""
        data = self.redis_client.hgetall(self.prefix + task_id)
        if not data:
            return None

        return TaskStatusResponse(
            task_id=task_id,
            status=TaskStatus(data.get("status", TaskStatus.PENDING.value)),
            progress=int(data.get("progress", 0)),
            current=data.get("current"),
            total_steps=int(data.get("total_steps", 100)) if data.get("total_steps") else None,
            result=json.loads(data["result"]) if data.get("result") else None,
            error=data.get("error"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
        )

    def cancel_task(self, task_id: str) -> bool:
        """Mark task as revoked (cancelled)."""
        data = self.redis_client.hgetall(self.prefix + task_id)
        if not data:
            return False

        self.redis_client.hset(
            self.prefix + task_id,
            mapping={
                "status": TaskStatus.REVOKED.value,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )
        return True

    def clear_task(self, task_id: str) -> bool:
        """Remove task data."""
        return bool(self.redis_client.delete(self.prefix + task_id))
