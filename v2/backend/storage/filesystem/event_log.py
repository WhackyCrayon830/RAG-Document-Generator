from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.storage.filesystem.json_store import read_json, write_json


def append_event(path: Path, event_type: str, message: str, metadata: dict[str, Any] | None = None) -> dict:
    events = read_json(path, [])
    event = {
        "time": datetime.now(UTC).isoformat(),
        "type": event_type,
        "message": message,
        "metadata": metadata or {},
    }
    events.append(event)
    write_json(path, events)
    return event
