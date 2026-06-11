from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
    settings = Settings()
    for path in [
        settings.app_storage_dir,
        settings.projects_dir,
        settings.vectors_dir,
        settings.templates_dir,
        settings.logs_dir,
        settings.generated_docs_dir,
        settings.app_storage_dir / "cache",
    ]:
        path.mkdir(parents=True, exist_ok=True)
    return settings
