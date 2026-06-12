"""API request/response models."""

from datetime import datetime
from enum import Enum
from typing import Optional
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


class GeneralSettings(BaseModel):
    """All configurable system settings exposed via the Settings UI."""
    ollama_base_url: Optional[str] = None
    ollama_planning_model: Optional[str] = None
    ollama_writing_model: Optional[str] = None
    ollama_validation_model: Optional[str] = None
    ollama_editing_model: Optional[str] = None
    ollama_embedding_model: Optional[str] = None
    use_ollama: Optional[bool] = None
    max_upload_mb: Optional[int] = None
    generation_timeout_seconds: Optional[int] = None
    worker_concurrency: Optional[int] = None
    max_concurrent_sections: Optional[int] = None
    app_storage_dir: Optional[str] = None
    redis_url: Optional[str] = None
    qdrant_url: Optional[str] = None
    postgres_host: Optional[str] = None
    postgres_port: Optional[int] = None
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None


class PullModelRequest(BaseModel):
    model: str


class SearchRequest(BaseModel):
    project_id: str
    query: str
    top_k: int = 8
