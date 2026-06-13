"""Task management utilities for async operations.

Supports two modes:
  - Redis mode (use_redis=True):  Uses Redis hash keys for distributed state.
  - In-memory mode (use_redis=False): Uses a thread-safe dict for single-process state.
"""

import json
import threading
from datetime import datetime
from typing import Any, Optional

from backend.config.settings import get_settings
from backend.api.models import TaskStatus, TaskStatusResponse


# ── In-memory fallback store ──────────────────────────────────────────────────
_memory_lock = threading.Lock()
_memory_tasks: dict[str, dict] = {}


class TaskTracker:
    """Track async task progress and results."""

    def __init__(self):
        settings = get_settings()
        self._use_redis = settings.use_redis
        if self._use_redis:
            import redis
            self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self.prefix = "task:"

    # ── Internal read/write helpers ───────────────────────────────────────────

    def _hset(self, task_id: str, mapping: dict) -> None:
        if self._use_redis:
            self.redis_client.hset(self.prefix + task_id, mapping=mapping)
        else:
            with _memory_lock:
                _memory_tasks.setdefault(self.prefix + task_id, {}).update(mapping)

    def _hgetall(self, task_id: str) -> dict:
        if self._use_redis:
            return self.redis_client.hgetall(self.prefix + task_id)
        with _memory_lock:
            return dict(_memory_tasks.get(self.prefix + task_id, {}))

    def _delete(self, task_id: str) -> bool:
        if self._use_redis:
            return bool(self.redis_client.delete(self.prefix + task_id))
        with _memory_lock:
            return bool(_memory_tasks.pop(self.prefix + task_id, None))

    # ── Public API ────────────────────────────────────────────────────────────

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
        self._hset(task_id, data)

    def update_progress(self, task_id: str, progress: int, current: str, total_steps: int = 100) -> None:
        """Update task progress."""
        self._hset(task_id, {
            "progress": str(progress),
            "current": current,
            "total_steps": str(total_steps),
        })

    def complete_task(self, task_id: str, result: dict) -> None:
        """Mark task as completed with result."""
        self._hset(task_id, {
            "status": TaskStatus.SUCCESS.value,
            "result": json.dumps(result),
            "progress": "100",
            "completed_at": datetime.utcnow().isoformat(),
        })

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed with error."""
        self._hset(task_id, {
            "status": TaskStatus.FAILURE.value,
            "error": error,
            "completed_at": datetime.utcnow().isoformat(),
        })

    def get_status(self, task_id: str) -> Optional[TaskStatusResponse]:
        """Retrieve task status."""
        data = self._hgetall(task_id)
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
        data = self._hgetall(task_id)
        if not data:
            return False
        self._hset(task_id, {
            "status": TaskStatus.REVOKED.value,
            "completed_at": datetime.utcnow().isoformat(),
        })
        return True

    def clear_task(self, task_id: str) -> bool:
        """Remove task data."""
        return self._delete(task_id)
