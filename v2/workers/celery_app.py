from celery import Celery

from backend.config.settings import get_settings


settings = get_settings()

if settings.use_redis:
    _broker = settings.redis_url
    _backend = settings.redis_url
else:
    _broker = "memory://"
    _backend = "cache+memory://"

celery_app = Celery(
    "rag_document_generator",
    broker=_broker,
    backend=_backend,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.generation_timeout_seconds,
    # In eager (no-redis) mode tasks execute synchronously in the caller's thread
    task_always_eager=not settings.use_redis,
    task_eager_propagates=not settings.use_redis,
)
