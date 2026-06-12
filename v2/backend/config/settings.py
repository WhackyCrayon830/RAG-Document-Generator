import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_config_dir() -> Path:
    user_profile = Path(os.getenv("USERPROFILE") or os.path.expanduser("~")).resolve()
    for candidate in [
        user_profile / "OneDrive" / "Documents",
        user_profile / "Documents",
    ]:
        if candidate.exists():
            cfg_dir = candidate / "RAG-Document-Generator"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            return cfg_dir
    cfg_dir = Path.home() / "RAG-Document-Generator"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


_CONFIG_DIR = get_config_dir()
_RUNTIME_SETTINGS_PATH = _CONFIG_DIR / "app_settings.json"


class Settings(BaseSettings):
    app_storage_dir: Path = Path("storage")
    ollama_base_url: str = "http://localhost:11434"
    ollama_planning_model: str = "qwen3:14b"
    ollama_writing_model: str = "qwen3:14b"
    ollama_validation_model: str = "gemma3:12b"
    ollama_editing_model: str = "mistral-small"
    ollama_embedding_model: str = "nomic-embed-text"
    use_ollama: bool = True
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "rag_platform"
    postgres_user: str = "rag"
    postgres_password: str = "rag_password"
    qdrant_url: str = "http://localhost:6333"
    redis_url: str = "redis://localhost:6379/0"
    max_upload_mb: int = 200
    generation_timeout_seconds: int = 1800
    worker_concurrency: int = 2
    max_concurrent_sections: int = 3

    model_config = SettingsConfigDict(env_file=str(_CONFIG_DIR / ".env"), env_file_encoding="utf-8")

    @property
    def projects_dir(self) -> Path:
        return self.app_storage_dir / "projects"

    @property
    def vectors_dir(self) -> Path:
        return self.app_storage_dir / "vectors"

    @property
    def templates_dir(self) -> Path:
        return self.app_storage_dir / "templates"

    @property
    def logs_dir(self) -> Path:
        return self.app_storage_dir / "logs"

    @property
    def generated_docs_dir(self) -> Path:
        return self.app_storage_dir / "generated_docs"


@lru_cache
def get_settings() -> Settings:
    base = Settings()
    for path in [
        base.app_storage_dir,
        base.projects_dir,
        base.vectors_dir,
        base.templates_dir,
        base.logs_dir,
        base.generated_docs_dir,
    ]:
        path.mkdir(parents=True, exist_ok=True)

    # Apply runtime overrides stored by the Settings UI
    if _RUNTIME_SETTINGS_PATH.exists():
        try:
            overrides: dict = json.loads(_RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
            for key, value in overrides.items():
                if hasattr(base, key):
                    try:
                        field_type = type(getattr(base, key))
                        object.__setattr__(base, key, field_type(value))
                    except Exception:
                        pass
        except Exception:
            pass

    return base


def save_runtime_settings(overrides: dict) -> dict:
    """Persist runtime setting overrides and refresh the cached Settings instance."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if _RUNTIME_SETTINGS_PATH.exists():
        try:
            existing = json.loads(_RUNTIME_SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing.update(overrides)
    _RUNTIME_SETTINGS_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    # Clear cache so next get_settings() picks up changes
    get_settings.cache_clear()

    # Apply immediately to the in-memory instance
    s = get_settings()
    return {k: str(getattr(s, k, "")) for k in existing}


def get_all_settings_dict() -> dict:
    """Return a serialisable snapshot of all configurable settings."""
    s = get_settings()
    return {
        "ollama_base_url": s.ollama_base_url,
        "ollama_planning_model": s.ollama_planning_model,
        "ollama_writing_model": s.ollama_writing_model,
        "ollama_validation_model": s.ollama_validation_model,
        "ollama_editing_model": s.ollama_editing_model,
        "ollama_embedding_model": s.ollama_embedding_model,
        "use_ollama": s.use_ollama,
        "max_upload_mb": s.max_upload_mb,
        "generation_timeout_seconds": s.generation_timeout_seconds,
        "worker_concurrency": s.worker_concurrency,
        "max_concurrent_sections": s.max_concurrent_sections,
        "app_storage_dir": str(s.app_storage_dir),
        "redis_url": s.redis_url,
        "qdrant_url": s.qdrant_url,
        "postgres_host": s.postgres_host,
        "postgres_port": s.postgres_port,
        "postgres_db": s.postgres_db,
        "postgres_user": s.postgres_user,
    }
