import logging
from pathlib import Path

from workers.celery_app import celery_app
from backend import services
from backend.api.task_tracker import TaskTracker

logger = logging.getLogger(__name__)


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
        tracker.update_progress(self.request.id, 20, "Parsing document…")
        result = services.ingest_file(project_id, Path(path), filename, embedding_model)
        tracker.update_progress(self.request.id, 100, "Ingestion complete")
        tracker.complete_task(self.request.id, result)
        return result
    except Exception as exc:
        logger.error("Ingestion task %s failed: %s", self.request.id, exc)
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
    """Generate a document asynchronously with real-time progress tracking."""
    tracker = TaskTracker()
    task_id = self.request.id
    try:
        tracker.start_task(
            task_id,
            "generate_document",
            {
                "project_id": project_id,
                "title": title,
                "prompt": prompt,
                "required_sections": required_sections,
            },
        )
        tracker.update_progress(task_id, 5, "Initialising pipeline…")

        # task_id is forwarded so the workflow can emit streaming events and
        # update progress in Redis throughout the async generation pipeline.
        result = services.generate_document(
            project_id,
            title,
            prompt,
            required_sections,
            template_id,
            model_overrides,
            task_id=task_id,
        )

        tracker.update_progress(task_id, 100, "Generation complete")
        tracker.complete_task(task_id, {
            "run_id": result["run_id"],
            "title": result["title"],
            "sections": len(result.get("sections", [])),
            "docx_path": result.get("docx_path", ""),
        })
        return result
    except Exception as exc:
        logger.error("Generation task %s failed: %s", task_id, exc)
        tracker.fail_task(task_id, str(exc))
        raise
