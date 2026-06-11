"""Streaming generation updates using WebSockets."""

from datetime import datetime
from typing import Callable, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class GenerationEventType(str, Enum):
    """Types of generation events."""
    STARTED = "generation.started"
    SECTION_PLANNING = "generation.section.planning"
    SECTION_STARTED = "generation.section.started"
    SECTION_WRITING = "generation.section.writing"
    SECTION_VALIDATING = "generation.section.validating"
    SECTION_COMPLETED = "generation.section.completed"
    EDITING = "generation.editing"
    PROGRESS = "generation.progress"
    ERROR = "generation.error"
    COMPLETED = "generation.completed"


@dataclass
class GenerationEvent:
    """A generation progress event."""
    type: GenerationEventType
    task_id: str
    timestamp: datetime
    progress: int  # 0-100
    message: str
    section_title: Optional[str] = None
    section_index: Optional[int] = None
    total_sections: Optional[int] = None
    data: Optional[dict] = None  # Additional context-specific data


class GenerationStreamManager:
    """Manage streaming updates for document generation."""

    def __init__(self):
        """Initialize stream manager."""
        self.connections: dict[str, list[Callable]] = {}  # task_id -> list of callbacks
        self.event_history: dict[str, list[GenerationEvent]] = {}  # task_id -> events
        self.max_history_size = 100

    def register_listener(self, task_id: str, callback: Callable[[GenerationEvent], None]) -> None:
        """
        Register a listener for generation events.

        Args:
            task_id: Task ID to listen to
            callback: Async callback function that receives events
        """
        if task_id not in self.connections:
            self.connections[task_id] = []
            self.event_history[task_id] = []

        self.connections[task_id].append(callback)
        logger.debug(f"Registered listener for task {task_id}")

    def unregister_listener(self, task_id: str, callback: Callable) -> None:
        """Unregister a listener."""
        if task_id in self.connections:
            try:
                self.connections[task_id].remove(callback)
                logger.debug(f"Unregistered listener for task {task_id}")
            except ValueError:
                pass

    async def emit_event(self, event: GenerationEvent) -> None:
        """
        Emit an event to all listeners.

        Args:
            event: The event to emit
        """
        # Store in history
        if event.task_id not in self.event_history:
            self.event_history[event.task_id] = []

        self.event_history[event.task_id].append(event)

        # Keep history size bounded
        if len(self.event_history[event.task_id]) > self.max_history_size:
            self.event_history[event.task_id].pop(0)

        # Emit to all listeners
        if event.task_id in self.connections:
            tasks = []
            for callback in self.connections[event.task_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        tasks.append(callback(event))
                    else:
                        callback(event)
                except Exception as exc:
                    logger.error(f"Error in callback: {exc}")

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def get_history(self, task_id: str) -> list[dict]:
        """Get event history for a task."""
        events = self.event_history.get(task_id, [])
        return [asdict(e) for e in events]

    def clear_history(self, task_id: str) -> None:
        """Clear event history for a task."""
        if task_id in self.event_history:
            self.event_history[task_id].clear()


# Global instance
_stream_manager = GenerationStreamManager()


def get_stream_manager() -> GenerationStreamManager:
    """Get the global stream manager."""
    return _stream_manager


async def emit_generation_started(task_id: str, total_sections: int) -> None:
    """Emit generation started event."""
    event = GenerationEvent(
        type=GenerationEventType.STARTED,
        task_id=task_id,
        timestamp=datetime.utcnow(),
        progress=0,
        message="Starting document generation",
        total_sections=total_sections,
    )
    await get_stream_manager().emit_event(event)


async def emit_section_planning(task_id: str, section_index: int, section_title: str) -> None:
    """Emit section planning event."""
    event = GenerationEvent(
        type=GenerationEventType.SECTION_PLANNING,
        task_id=task_id,
        timestamp=datetime.utcnow(),
        progress=0,
        message=f"Planning section: {section_title}",
        section_title=section_title,
        section_index=section_index,
    )
    await get_stream_manager().emit_event(event)


async def emit_section_writing(task_id: str, section_index: int, section_title: str) -> None:
    """Emit section writing event."""
    event = GenerationEvent(
        type=GenerationEventType.SECTION_WRITING,
        task_id=task_id,
        timestamp=datetime.utcnow(),
        progress=0,
        message=f"Writing section: {section_title}",
        section_title=section_title,
        section_index=section_index,
    )
    await get_stream_manager().emit_event(event)


async def emit_section_validating(task_id: str, section_index: int, section_title: str) -> None:
    """Emit section validation event."""
    event = GenerationEvent(
        type=GenerationEventType.SECTION_VALIDATING,
        task_id=task_id,
        timestamp=datetime.utcnow(),
        progress=0,
        message=f"Validating section: {section_title}",
        section_title=section_title,
        section_index=section_index,
    )
    await get_stream_manager().emit_event(event)


async def emit_section_completed(
    task_id: str,
    section_index: int,
    section_title: str,
    content: str,
) -> None:
    """Emit section completed event."""
    event = GenerationEvent(
        type=GenerationEventType.SECTION_COMPLETED,
        task_id=task_id,
        timestamp=datetime.utcnow(),
        progress=0,
        message=f"Completed section: {section_title}",
        section_title=section_title,
        section_index=section_index,
        data={"content_length": len(content)},
    )
    await get_stream_manager().emit_event(event)


async def emit_progress(task_id: str, progress: int, message: str) -> None:
    """Emit progress event."""
    event = GenerationEvent(
        type=GenerationEventType.PROGRESS,
        task_id=task_id,
        timestamp=datetime.utcnow(),
        progress=progress,
        message=message,
    )
    await get_stream_manager().emit_event(event)


async def emit_generation_completed(task_id: str, document_data: dict) -> None:
    """Emit generation completed event."""
    event = GenerationEvent(
        type=GenerationEventType.COMPLETED,
        task_id=task_id,
        timestamp=datetime.utcnow(),
        progress=100,
        message="Document generation completed",
        data=document_data,
    )
    await get_stream_manager().emit_event(event)


async def emit_generation_error(task_id: str, error: str) -> None:
    """Emit generation error event."""
    event = GenerationEvent(
        type=GenerationEventType.ERROR,
        task_id=task_id,
        timestamp=datetime.utcnow(),
        progress=0,
        message=f"Error: {error}",
        data={"error": error},
    )
    await get_stream_manager().emit_event(event)
