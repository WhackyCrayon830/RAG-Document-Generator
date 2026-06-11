from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.projects import router as project_router
from backend.api.routes.streaming import router as streaming_router
from backend.health import deep_health

app = FastAPI(title="Offline RAG Document Generator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(project_router)
app.include_router(streaming_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "offline-first", "llm": "ollama"}


@app.get("/health/deep")
def health_deep() -> dict:
    return deep_health()
