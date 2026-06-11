"""API request/response models."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class TaskStatus(str, Enum):
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    REVOKED = "revoked"


class TaskResponse(BaseModel):
    """Response for async task submission."""
    task_id: str
    status: TaskStatus
    message: str | None = None
    created_at: datetime


class TaskStatusResponse(BaseModel):
    """Response for task status polling."""
    task_id: str
    status: TaskStatus
    progress: int | None = None  # 0-100
    current: str | None = None  # Current step description
    total_steps: int | None = None
    result: dict | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CancellationResponse(BaseModel):
    """Response for task cancellation."""
    task_id: str
    status: str
    message: str


class ProjectCreate(BaseModel):
    name: str


class GenerateRequest(BaseModel):
    project_id: str
    title: str
    prompt: str
    required_sections: list[str] | None = None
    template_id: str | None = None
    model_overrides: dict | None = None


class ModelSettings(BaseModel):
    embedding_model: str | None = None
    planning_model: str | None = None
    writing_model: str | None = None
    validation_model: str | None = None
    editing_model: str | None = None


class PullModelRequest(BaseModel):
    model: str


class SearchRequest(BaseModel):
    project_id: str
    query: str
    top_k: int = 8
