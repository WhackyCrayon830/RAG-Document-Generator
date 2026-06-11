from pathlib import Path

from workers.celery_app import celery_app
from backend import services
from backend.api.task_tracker import TaskTracker


@celery_app.task(name="ingest_document", bind=True)
def ingest_document(
    self,
    project_id: str,
    path: str,
    filename: str,
    embedding_model: str | None = None,
) -> dict:
    """Ingest a document asynchronously."""
    tracker = TaskTracker()
    try:
        tracker.start_task(
            self.request.id,
            "ingest_document",
            {"project_id": project_id, "filename": filename, "embedding_model": embedding_model},
        )
        tracker.update_progress(self.request.id, 20, "Parsing document...")
        result = services.ingest_file(project_id, Path(path), filename, embedding_model)
        tracker.update_progress(self.request.id, 100, "Ingestion complete")
        tracker.complete_task(self.request.id, result)
        return result
    except Exception as exc:
        tracker.fail_task(self.request.id, str(exc))
        raise


@celery_app.task(name="generate_document", bind=True)
def generate_document(
    self,
    project_id: str,
    title: str,
    prompt: str,
    required_sections: list[str] | None = None,
    template_id: str | None = None,
    model_overrides: dict | None = None,
) -> dict:
    """Generate a document asynchronously."""
    tracker = TaskTracker()
    try:
        tracker.start_task(
            self.request.id,
            "generate_document",
            {
                "project_id": project_id,
                "title": title,
                "prompt": prompt,
                "required_sections": required_sections,
            },
        )
        tracker.update_progress(self.request.id, 10, "Planning document structure...")
        result = services.generate_document(project_id, title, prompt, required_sections, template_id, model_overrides)
        tracker.update_progress(self.request.id, 100, "Generation complete")
        tracker.complete_task(self.request.id, result)
        return result
    except Exception as exc:
        tracker.fail_task(self.request.id, str(exc))
        raise
