from pathlib import Path
from uuid import uuid4

from backend.agents.editor.agent import EditorAgent
from backend.agents.ollama_client import OllamaClient
from backend.agents.planner.agent import PlannerAgent
from backend.agents.retriever.agent import RetrieverAgent
from backend.agents.validator.agent import ValidatorAgent
from backend.agents.writer.agent import WriterAgent
from backend.config.settings import get_settings
from backend.ingestion.chunking.text_chunker import chunk_text
from backend.ingestion.embeddings.local_embeddings import EmbeddingClient
from backend.ingestion.hashing.sha256 import file_sha256
from backend.ingestion.parsers.document_parser import SUPPORTED_EXTENSIONS
from backend.ingestion.raganything.adapter import RagAnythingAdapter
from backend.orchestration.workflows.document_generation import DocumentGenerationWorkflow
from backend.retrieval.hybrid.local_vector_store import LocalVectorStore
from backend.storage.filesystem.event_log import append_event
from backend.storage.filesystem.json_store import read_json, write_json
from backend.storage.filesystem.project_layout import ensure_project_layout
from backend.templates.extraction.docx_template import extract_template_profile


settings = get_settings()


def model_config_path() -> Path:
    return settings.app_storage_dir / "cache" / "model_settings.json"


def get_model_config() -> dict:
    return read_json(
        model_config_path(),
        {
            "embedding_model": settings.ollama_embedding_model,
            "planning_model": settings.ollama_planning_model,
            "writing_model": settings.ollama_writing_model,
            "validation_model": settings.ollama_validation_model,
            "editing_model": settings.ollama_editing_model,
        },
    )


def save_model_config(payload: dict) -> dict:
    current = get_model_config()
    for key in ["embedding_model", "planning_model", "writing_model", "validation_model", "editing_model"]:
        if payload.get(key):
            current[key] = payload[key]
    write_json(model_config_path(), current)
    return current


def project_dir(project_id: str) -> Path:
    return settings.projects_dir / project_id


def project_meta_path(project_id: str) -> Path:
    return project_dir(project_id) / "project.json"


def create_project(name: str) -> dict:
    project_id = str(uuid4())
    root = project_dir(project_id)
    ensure_project_layout(root)
    project = {"id": project_id, "name": name, "documents": [], "templates": []}
    write_json(project_meta_path(project_id), project)
    append_event(root / "logs" / "events.json", "project.created", f"Created project {name}", {"project_id": project_id})
    return project


def list_projects() -> list[dict]:
    return [
        read_json(path / "project.json", {})
        for path in settings.projects_dir.glob("*")
        if (path / "project.json").exists()
    ]


def get_project(project_id: str) -> dict:
    return read_json(project_meta_path(project_id), {})


def ingest_file(project_id: str, source_path: Path, filename: str, embedding_model: str | None = None) -> dict:
    if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    root = project_dir(project_id)
    layout = ensure_project_layout(root)
    project = get_project(project_id)
    file_hash = file_sha256(source_path)
    existing = next((doc for doc in project.get("documents", []) if doc["sha256"] == file_hash), None)
    if existing:
        append_event(root / "logs" / "events.json", "ingestion.skipped", f"Skipped duplicate {filename}", {"sha256": file_hash})
        return {"status": "skipped", "document": existing, "chunks_added": 0}

    document_id = str(uuid4())
    upload_path = layout["raw"] / f"{document_id}{source_path.suffix.lower()}"
    upload_path.write_bytes(source_path.read_bytes())

    parser = RagAnythingAdapter()
    text = parser.parse(upload_path)
    chunks = chunk_text(text)
    parsed_record = {
        "document_id": document_id,
        "filename": filename,
        "sha256": file_hash,
        "text": text,
        "chunks": [{"index": chunk.index, "text": chunk.text} for chunk in chunks],
        "layout": {},
        "tables": [],
        "images": [],
        "ocr": [],
    }
    write_json(layout["parsed"] / f"{document_id}.json", parsed_record)
    model_config = get_model_config()
    embeddings = EmbeddingClient(
        settings.ollama_base_url,
        embedding_model or model_config["embedding_model"],
        settings.use_ollama,
    )
    vector_store = LocalVectorStore(settings.vectors_dir / f"{project_id}.json")

    for chunk in chunks:
        chunk_id = f"{document_id}:{chunk.index}"
        vector_store.add_chunk(
            chunk_id,
            document_id,
            chunk.text,
            embeddings.embed(chunk.text),
            {"filename": filename, "sha256": file_hash, "chunk_index": chunk.index, "modality": "text"},
        )
    vector_store.save()

    document = {
        "id": document_id,
        "filename": filename,
        "sha256": file_hash,
        "path": str(upload_path),
        "parsed_path": str(layout["parsed"] / f"{document_id}.json"),
        "chunks": len(chunks),
        "version": 1,
    }
    project.setdefault("documents", []).append(document)
    write_json(project_meta_path(project_id), project)
    append_event(root / "logs" / "events.json", "ingestion.completed", f"Ingested {filename}", {"chunks": len(chunks)})
    return {"status": "ingested", "document": document, "chunks_added": len(chunks)}


def save_template(project_id: str, source_path: Path, filename: str) -> dict:
    template_id = str(uuid4())
    root = project_dir(project_id)
    layout = ensure_project_layout(root)
    target = layout["templates"] / f"{template_id}.docx"
    target.write_bytes(source_path.read_bytes())
    profile = extract_template_profile(target)
    template = {"id": template_id, "filename": filename, "path": str(target), "profile": profile}
    project = get_project(project_id)
    project.setdefault("templates", []).append(template)
    write_json(project_meta_path(project_id), project)
    write_json(layout["cache"] / f"template_{template_id}_stylegraph.json", profile)
    append_event(root / "logs" / "events.json", "template.saved", f"Saved template {filename}", {"template_id": template_id})
    return template


def build_workflow(project_id: str, model_overrides: dict | None = None) -> DocumentGenerationWorkflow:
    model_config = {**get_model_config(), **(model_overrides or {})}
    ollama = OllamaClient(settings.ollama_base_url, settings.use_ollama)
    embeddings = EmbeddingClient(settings.ollama_base_url, model_config["embedding_model"], settings.use_ollama)
    vector_store = LocalVectorStore(settings.vectors_dir / f"{project_id}.json")
    retriever = RetrieverAgent(embeddings, vector_store)
    return DocumentGenerationWorkflow(
        PlannerAgent(ollama, settings, model_config["planning_model"]),
        retriever,
        WriterAgent(ollama, settings, model_config["writing_model"]),
        ValidatorAgent(ollama, settings, model_config["validation_model"]),
        EditorAgent(ollama, settings, model_config["editing_model"]),
        max_concurrent=settings.max_concurrent_sections,
    )


def generate_document(
    project_id: str,
    title: str,
    prompt: str,
    required_sections: list[str] | None,
    template_id: str | None,
    model_overrides: dict | None = None,
    task_id: str | None = None,
) -> dict:
    project = get_project(project_id)
    template_path = None
    if template_id:
        template = next((item for item in project.get("templates", []) if item["id"] == template_id), None)
        template_path = Path(template["path"]) if template else None
    workflow = build_workflow(project_id, model_overrides)
    return workflow.run(project_dir(project_id), title, prompt, required_sections, template_path, task_id=task_id)


def search_project(project_id: str, query: str, top_k: int = 8) -> list[dict]:
    model_config = get_model_config()
    embeddings = EmbeddingClient(settings.ollama_base_url, model_config["embedding_model"], settings.use_ollama)
    vector_store = LocalVectorStore(settings.vectors_dir / f"{project_id}.json")
    results = vector_store.hybrid_search(query, embeddings.embed(query), top_k=top_k)
    return [
        {
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "text": item.text,
            "score": item.score,
            "metadata": item.metadata,
        }
        for item in results
    ]


def project_events(project_id: str) -> list[dict]:
    return read_json(project_dir(project_id) / "logs" / "events.json", [])
