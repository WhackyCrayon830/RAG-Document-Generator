import logging
import logging.handlers
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.projects import router as project_router
from backend.api.routes.streaming import router as streaming_router
from backend.health import deep_health


def _setup_logging() -> None:
    """Configure logging to write to file and stdout."""
    log_dir = Path(os.getenv("APP_STORAGE_DIR", "storage")) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler – keeps last 5 × 5 MB
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Stream handler for console output
    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)

    if not root_logger.handlers:
        root_logger.addHandler(fh)
        root_logger.addHandler(sh)


_setup_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="Offline RAG Document Generator", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(project_router)
app.include_router(streaming_router)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("RAG Document Generator backend started")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "offline-first", "llm": "ollama"}


@app.get("/health/deep")
def health_deep() -> dict:
    return deep_health()
