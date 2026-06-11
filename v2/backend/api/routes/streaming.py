"""WebSocket endpoints for streaming generation updates."""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
import logging

from backend.streaming import get_stream_manager, GenerationEvent

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """Accept and register a connection."""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)
        logger.info(f"Client connected to task {task_id}")

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """Remove a connection."""
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
        logger.info(f"Client disconnected from task {task_id}")

    async def broadcast(self, task_id: str, data: dict) -> None:
        """Send message to all clients connected to a task."""
        if task_id not in self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections[task_id]:
            try:
                await connection.send_json(data)
            except Exception as exc:
                logger.error(f"Error sending to client: {exc}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(task_id, connection)


manager = ConnectionManager()


@router.websocket("/ws/generation/{task_id}")
async def websocket_generation(websocket: WebSocket, task_id: str) -> None:
    """
    WebSocket endpoint for streaming generation updates.

    Clients connect with task_id and receive real-time generation progress.
    """
    await manager.connect(task_id, websocket)

    try:
        # Send any cached events first
        stream_manager = get_stream_manager()
        history = stream_manager.get_history(task_id)
        
        for event_dict in history:
            await websocket.send_json({
                "type": "cached_event",
                "event": event_dict,
            })

        # Register a callback to push new events to this client
        async def on_event(event: GenerationEvent) -> None:
            try:
                await websocket.send_json({
                    "type": "event",
                    "event": {
                        "type": event.type.value,
                        "task_id": event.task_id,
                        "timestamp": event.timestamp.isoformat(),
                        "progress": event.progress,
                        "message": event.message,
                        "section_title": event.section_title,
                        "section_index": event.section_index,
                        "total_sections": event.total_sections,
                        "data": event.data,
                    },
                })
            except Exception as exc:
                logger.debug(f"Error sending event to client: {exc}")

        stream_manager.register_listener(task_id, on_event)

        # Keep connection open
        while True:
            data = await websocket.receive_text()
            
            # Handle client messages (e.g., health checks, cancellation)
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif message.get("type") == "cancel":
                    # Could implement cancellation logic here
                    logger.info(f"Cancel request for task {task_id}")
                    
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")

    except WebSocketDisconnect:
        manager.disconnect(task_id, websocket)
        stream_manager = get_stream_manager()
        stream_manager.unregister_listener(task_id, lambda e: None)
    except Exception as exc:
        logger.error(f"WebSocket error: {exc}")
        manager.disconnect(task_id, websocket)


@router.get("/stream/{task_id}/history")
def get_event_history(task_id: str) -> list[dict]:
    """
    Get cached event history for a task.

    Useful for clients that connect after generation has started.
    """
    stream_manager = get_stream_manager()
    return stream_manager.get_history(task_id)


@router.delete("/stream/{task_id}/history")
def clear_event_history(task_id: str) -> dict:
    """Clear cached event history for a task."""
    stream_manager = get_stream_manager()
    stream_manager.clear_history(task_id)
    return {"status": "cleared", "task_id": task_id}
