from celery import Celery

from backend.config.settings import get_settings


settings = get_settings()

celery_app = Celery(
    "rag_document_generator",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.generation_timeout_seconds,
)
