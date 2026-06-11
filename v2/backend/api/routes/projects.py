from pathlib import Path
from tempfile import NamedTemporaryFile
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
import requests

from backend import services
from backend.config.settings import get_settings
from backend.api.models import (
    ProjectCreate,
    GenerateRequest,
    ModelSettings,
    PullModelRequest,
    SearchRequest,
    TaskResponse,
    TaskStatus,
)
from backend.api.task_tracker import TaskTracker
from workers.celery_app import celery_app
from workers import tasks as task_module

router = APIRouter()


@router.get("/projects")
def list_projects() -> list[dict]:
    return services.list_projects()


@router.post("/projects")
def create_project(payload: ProjectCreate) -> dict:
    return services.create_project(payload.name)


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    project = services.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# === Synchronous endpoints (for backward compatibility) ===

@router.post("/upload")
async def upload(
    project_id: str = Form(...),
    embedding_model: str | None = Form(None),
    file: UploadFile = File(...),
) -> dict:
    settings = get_settings()
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB upload limit")
    suffix = Path(file.filename or "upload").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        return services.ingest_file(project_id, tmp_path, file.filename or tmp_path.name, embedding_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/template")
async def upload_template(project_id: str = Form(...), file: UploadFile = File(...)) -> dict:
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Templates must be DOCX files")
    with NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        return services.save_template(project_id, tmp_path, file.filename or "template.docx")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/generate")
def generate(payload: GenerateRequest) -> dict:
    return services.generate_document(
        payload.project_id,
        payload.title,
        payload.prompt,
        payload.required_sections,
        payload.template_id,
        payload.model_overrides,
    )


# === Asynchronous endpoints ===

@router.post("/upload/async")
async def upload_async(
    project_id: str = Form(...),
    embedding_model: str | None = Form(None),
    file: UploadFile = File(...),
) -> TaskResponse:
    """Upload and ingest a document asynchronously."""
    settings = get_settings()
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB upload limit")
    
    suffix = Path(file.filename or "upload").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    
    try:
        # Submit async task
        result = celery_app.send_task(
            "ingest_document",
            args=(project_id, str(tmp_path), file.filename or tmp_path.name),
            kwargs={"embedding_model": embedding_model},
        )
        
        return TaskResponse(
            task_id=result.id,
            status=TaskStatus.PENDING,
            message="Document ingestion queued",
            created_at=datetime.utcnow(),
        )
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue ingestion: {str(exc)}") from exc


@router.post("/generate/async")
def generate_async(payload: GenerateRequest) -> TaskResponse:
    """Generate a document asynchronously."""
    try:
        result = celery_app.send_task(
            "generate_document",
            args=(
                payload.project_id,
                payload.title,
                payload.prompt,
            ),
            kwargs={
                "required_sections": payload.required_sections,
                "template_id": payload.template_id,
                "model_overrides": payload.model_overrides,
            },
        )
        
        return TaskResponse(
            task_id=result.id,
            status=TaskStatus.PENDING,
            message="Document generation queued",
            created_at=datetime.utcnow(),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to queue generation: {str(exc)}") from exc


@router.get("/tasks/{task_id}/status")
def get_task_status(task_id: str):
    """Get the status of an async task."""
    tracker = TaskTracker()
    status = tracker.get_status(task_id)
    
    if not status:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return status


@router.delete("/tasks/{task_id}")
def cancel_task(task_id: str) -> dict:
    """Cancel a running task."""
    try:
        # Revoke the Celery task
        celery_app.control.revoke(task_id, terminate=True)
        
        # Mark as revoked in tracker
        tracker = TaskTracker()
        tracker.cancel_task(task_id)
        
        return {"task_id": task_id, "status": "revoked", "message": "Task cancellation requested"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(exc)}") from exc


# === Export endpoints ===

@router.post("/projects/{project_id}/export/{run_id}/pdf")
def export_pdf(project_id: str, run_id: str) -> FileResponse:
    """Export a generated document as PDF."""
    try:
        # Get document info from the project
        project_dir = services.project_dir(project_id)
        sections_file = project_dir / "runs" / f"{run_id}_sections.json"
        
        if not sections_file.exists():
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Load sections
        import json
        with open(sections_file) as f:
            data = json.load(f)
        
        # Generate PDF
        from backend.exporters.pdf import compile_pdf
        output_path = project_dir / "exports" / f"{run_id}.pdf"
        compile_pdf(data.get("title", "Document"), data.get("sections", []), output_path)
        
        return FileResponse(output_path, filename=f"{run_id}.pdf", media_type="application/pdf")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(exc)}") from exc


@router.get("/download/{project_id}/{run_id}")
def download(project_id: str, run_id: str) -> FileResponse:
    path = services.project_dir(project_id) / "generated" / f"{run_id}.docx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(path, filename=f"{run_id}.docx")


@router.post("/retrieval/search")
def search(payload: SearchRequest) -> list[dict]:
    return services.search_project(payload.project_id, payload.query, payload.top_k)


@router.get("/projects/{project_id}/events")
def events(project_id: str) -> list[dict]:
    return services.project_events(project_id)


@router.get("/settings/models")
def get_model_settings() -> dict:
    return services.get_model_config()


@router.post("/settings/models")
def save_model_settings(payload: ModelSettings) -> dict:
    return services.save_model_config(payload.model_dump(exclude_none=True))


@router.get("/ollama/models")
def list_ollama_models() -> dict:
    settings = get_settings()
    try:
        response = requests.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=8)
        response.raise_for_status()
        models = [item["name"] for item in response.json().get("models", [])]
        return {"available": True, "base_url": settings.ollama_base_url, "models": models}
    except requests.RequestException as exc:
        return {"available": False, "base_url": settings.ollama_base_url, "models": [], "error": str(exc)}


@router.post("/ollama/pull")
def pull_ollama_model(payload: PullModelRequest) -> dict:
    settings = get_settings()
    try:
        response = requests.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/pull",
            json={"name": payload.model, "stream": False},
            timeout=1800,
        )
        response.raise_for_status()
        return {"status": "complete", "model": payload.model, "details": response.json()}
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Ollama pull failed: {exc}") from exc
