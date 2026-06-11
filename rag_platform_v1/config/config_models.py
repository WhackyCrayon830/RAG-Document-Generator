"""
Pydantic config models for type-safe configuration management.
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class AppConfig(BaseModel):
    title: str = "RAG Platform"
    version: str = "1.0.0"
    default_chunk_size: int = 512
    default_chunk_overlap: int = 64
    default_top_k: int = 5
    max_chat_history: int = 20


class FAISSConfig(BaseModel):
    index_path: str = "vector_db/faiss.index"
    metadata_path: str = "vector_db/metadata.pkl"


class ModelsConfig(BaseModel):
    embedding_models: List[str] = Field(
        default=["sentence-transformers/all-MiniLM-L6-v2"]
    )
    online_models: List[str] = Field(default=[])


class PlatformConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    faiss: FAISSConfig = Field(default_factory=FAISSConfig)


def load_platform_config(path: str = "config/app_config.json") -> PlatformConfig:
    import json, os
    if not os.path.exists(path):
        return PlatformConfig()
    with open(path) as f:
        data = json.load(f)
    return PlatformConfig(**data)


def load_models_config(path: str = "config/models_config.json") -> ModelsConfig:
    import json, os
    if not os.path.exists(path):
        return ModelsConfig()
    with open(path) as f:
        data = json.load(f)
    return ModelsConfig(**data)
