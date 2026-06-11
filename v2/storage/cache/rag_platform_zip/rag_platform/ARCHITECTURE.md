# Architecture Overview

## System Design

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Frontend                       │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ Sidebar  │  │ Chat Mode    │  │ Doc Generation Mode    │ │
│  │ Controls │  │ (RAG + cite) │  │ (Markdown + Export)    │ │
│  └──────────┘  └──────────────┘  └────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                      Core Services                           │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Ingestion  │  │  Retrieval   │  │   Generation      │  │
│  │  Engine     │  │  (FAISS)     │  │   (LLM)           │  │
│  └──────┬──────┘  └──────┬───────┘  └────────┬──────────┘  │
└─────────┼────────────────┼───────────────────┼─────────────┘
          │                │                   │
┌─────────▼──────┐  ┌──────▼───────┐  ┌───────▼────────────┐
│ Plugin System  │  │ Vector Store │  │ LLM Manager        │
│ ┌────────────┐ │  │ (FAISS+CPU)  │  │ ┌────────────────┐ │
│ │ PDF Plugin │ │  │              │  │ │ Offline (local)│ │
│ │ DOCX Plugin│ │  │ Embeddings:  │  │ │ Online (HF API)│ │
│ │ MD Plugin  │ │  │ SentTrans    │  │ └────────────────┘ │
│ │ CSV Plugin │ │  │              │  │                    │
│ │ XLSX Plugin│ │  │ Persist to   │  │ Models:            │
│ │ HTML Plugin│ │  │ vector_db/   │  │ Phi, Qwen,         │
│ │ TXT Plugin │ │  │              │  │ Mistral, DeepSeek  │
│ │ + YOUR     │ │  └──────────────┘  └────────────────────┘
│ │   PLUGINS  │ │
│ └────────────┘ │
└────────────────┘
```

## Data Flow

### Ingestion Pipeline
```
File Upload
    │
    ▼
Plugin Registry (auto-detects extension)
    │
    ▼
Plugin.extract() → List[DocumentChunk]
    │
    ▼
Chunker (recursive / token-aware)
    │
    ▼
SentenceTransformer.encode() → embeddings
    │
    ▼
FAISS.add() + metadata list
    │
    ▼
Persist to disk (vector_db/)
```

### RAG Query Pipeline
```
User Question
    │
    ▼
SentenceTransformer.encode(question) → query embedding
    │
    ▼
FAISS.search() → top-K similar chunks
    │
    ▼
Confidence scoring (L2 distance → high/medium/low)
    │
    ▼
Build prompt with context + chat history
    │
    ▼
LLM.generate() → streaming tokens
    │
    ▼
Stream to UI with source citations
```

## Plugin System

Each plugin is a self-contained Python file in `plugins/`.
The `PluginRegistry` auto-discovers all subclasses of `BasePlugin`
using Python's `pkgutil.iter_modules` at startup.

```python
# Adding a new plugin is this simple:
class AudioPlugin(BasePlugin):
    SUPPORTED_EXTENSIONS = [".mp3", ".wav"]

    def extract(self, file_path: str) -> List[DocumentChunk]:
        # transcribe with whisper, return chunks
        ...
```

No changes to any other file are needed.

## CPU/GPU Strategy

- Hardware is detected once at startup via `services/hardware_detector.py`
- SentenceTransformer embeddings auto-select `device=cuda` or `device=cpu`
- Transformers pipeline uses `device=0` (GPU) or `device=-1` (CPU)
- Batch sizes are scaled up for GPU automatically
- System degrades gracefully to CPU if CUDA unavailable

## Offline vs Online Mode

| Feature | Offline | Online |
|---------|---------|--------|
| Model location | `models/<name>/` | HuggingFace API |
| Token required | No | Yes |
| Latency | Higher (CPU) | Lower |
| Privacy | Full (no internet) | Requires connection |
| Cost | Free | Free tier limits |

## Session State Management

Streamlit reruns the entire script on every interaction.
All mutable state is stored in `st.session_state` with default
values initialised once at the top of `app.py`. Heavy objects
(vector store, LLM) are cached via `@st.cache_resource`.
