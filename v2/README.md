# RAG Document Generator

A powerful offline document generation platform that leverages local LLMs and retrieval-augmented generation to create high-quality documents from your data.

**Status:** ✅ Production Ready | **Last Updated:** June 11, 2026

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Architecture](#architecture)
4. [Quick Start](#quick-start)
5. [API Reference](#api-reference)
6. [Configuration](#configuration)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

The RAG Document Generator combines local LLMs (via Ollama), vector databases, and intelligent orchestration to create well-structured documents without external API dependencies. Perfect for organizations needing privacy-preserving document generation.

**Key Characteristics:**
- **Local-First:** No cloud services required
- **Extensible:** Pluggable agents and storage backends
- **Production-Ready:** Comprehensive error handling and logging
- **Async-Capable:** Long-running operations with progress tracking
- **Real-Time Updates:** WebSocket streaming of generation progress

---

## ✨ Features

### Core Features

#### 1. Project-Based Document Management
- Organize documents by projects
- Persistent storage under `storage/projects`
- Per-project: raw documents, parsed artifacts, templates, generated output, logs, and cache
- Event logging for audit trails

#### 2. Document Ingestion & Parsing
- **Format Support:** PDF, DOCX, TXT, Markdown
- **Incremental Ingestion:** SHA256-based duplicate detection
- **Multimodal Processing:**
  - OCR for scanned documents (PaddleOCR with Tesseract fallback)
  - Table extraction and structuring
  - Image extraction with auto-captioning
  - Layout analysis for complex documents

#### 3. Intelligent Retrieval
- **Hybrid Search:** Vector similarity + keyword overlap
- **Local Embeddings:** Ollama-based or fallback hash-based
- **Vector Storage:** JSON-based local store (Qdrant available)
- **Scope & Filtering:** Retrieval scoped by project and document

#### 4. Section-Wise Document Generation
- **Workflow:** Planning → Retrieval → Writing → Validation → Editing
- **Agents:**
  - **Planner:** Creates document structure and section outlines
  - **Retriever:** Fetches relevant context for each section
  - **Writer:** Generates section content using Ollama
  - **Validator:** Checks quality and suggests revisions
  - **Editor:** Polishes final document

#### 5. Async Job Processing ⭐ (New)
- Submit long-running tasks without blocking
- Real-time progress tracking via Redis
- Task cancellation support
- Endpoints:
  - `POST /upload/async` - Queue document ingestion
  - `POST /generate/async` - Queue document generation
  - `GET /tasks/{task_id}/status` - Poll task status
  - `DELETE /tasks/{task_id}` - Cancel task

#### 6. Real-Time Streaming Updates ⭐ (New)
- WebSocket connection for live generation progress
- 9 event types covering entire lifecycle
- Event history for late-connecting clients
- Endpoints:
  - `ws://localhost:8000/ws/generation/{task_id}` - Live updates
  - `GET /stream/{task_id}/history` - Event history
  - `DELETE /stream/{task_id}/history` - Clear history

#### 7. Intelligent Validation ⭐ (New)
- **Validation Checks:**
  - Content length (minimum 50 characters)
  - Coherence and logical structure
  - Citation presence in source documents
  - Formatting consistency
  - Hallucination detection
- **Output:**
  - Issue classification (ERROR/WARNING/INFO)
  - Rewrite suggestions
  - Confidence scoring (0-1)
  - 3-iteration recursive validation

#### 8. PDF Export ⭐ (New)
- Professional PDF generation using ReportLab
- Consistent styling with DOCX output
- Support for Letter and A4 page sizes
- Endpoint: `POST /projects/{id}/export/{id}/pdf`

#### 9. Parallel Section Generation ⭐ (New)
- Generate multiple sections concurrently
- Dependency tracking between sections
- Circular dependency detection
- Context passing between sections
- Configurable parallelization (default: 3 concurrent)

#### 10. Backup & Data Management ⭐ (New)
- Project backup/restore with timestamps
- Old run cleanup (configurable retention)
- Cache cleanup and optimization
- Orphaned vector detection
- Project archival
- Storage statistics and analysis

#### 11. DOCX Export & Templates
- Template upload with style extraction
- Placeholder support for dynamic content
- Header/footer injection
- Table and list preservation
- Custom numbering styles

#### 12. Dashboard Interface
- Streamlit-based web UI
- Document management view
- Generation workflow
- Model management
- Retrieval testing
- Project event viewing

---

## 🏗️ Architecture

### System Components

```
┌─────────────────┐
│   Streamlit UI  │
└────────┬────────┘
         │
    ┌────▼────────────────┐
    │   FastAPI Backend   │
    └────┬────────────────┘
         │
    ┌────┼─────────────────────────┐
    │    │                         │
┌───▼──┐ │  ┌──────────────┐  ┌──▼──────┐
│Redis ├─┤  │   Celery     │  │Ollama   │
│      │ │  │   Workers    │  │(LLM)    │
└──────┘ │  └──────────────┘  └─────────┘
         │
    ┌────▼──────────────┐
    │ Storage Layer     │
    ├──────────────────┤
    │ - JSON Store     │
    │ - Vector Index   │
    │ - PostgreSQL*    │
    │ - Qdrant*        │
    └──────────────────┘

* Available for production deployment
```

### Data Flow

**Ingestion Pipeline:**
```
Upload File → Parser → Chunking → Embedding → Store
                ↓
           SHA256 Hash
              ↓
        (Skip if duplicate)
```

**Generation Pipeline:**
```
User Request → Planner → [For Each Section]:
                           ├→ Retriever
                           ├→ Writer
                           ├→ Validator
                           └→ Editor
                         ↓
                    DOCX/PDF Export
```

**Async Processing:**
```
API Request → Celery Queue → Redis Broker → Worker Process
                                  ↑
                            Task Tracker
                                  ↓
                         WebSocket Events
                                  ↓
                            Client Updates
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+**
- **Conda** (recommended) or pip
- **Ollama** (optional, for LLM features)
- **Redis** (for async support)
- **Docker** (optional, for running services)

### Option 1: Fast Path with Launcher

```powershell
.\launch.ps1
```

The launcher:
- ✅ Checks and creates conda environment
- ✅ Starts Ollama if available
- ✅ Pulls required models
- ✅ Starts Celery worker in background
- ✅ Starts FastAPI backend
- ✅ Starts Streamlit frontend
- ✅ Opens browser to dashboard

**Run Tests:**
```powershell
.\launch.ps1 -Test
# or
.\launch.ps1 --test
```

**Skip Model Pull:**
```powershell
.\launch.ps1 -SkipModelPull
```

**Skip Browser:**
```powershell
.\launch.ps1 -NoBrowser
```

**Skip Celery:**
```powershell
.\launch.ps1 -NoCelery
```

### Option 2: Manual Setup

**1. Create Conda Environment:**
```bash
conda env create -f environment.yml
conda activate rag_document_generator
```

**2. Install Dependencies:**
```bash
pip install -r requirements.txt
```

**3. Start Redis (required for async):**
```bash
# Docker
docker run -d -p 6379:6379 redis:latest

# Or use system Redis
redis-server
```

**4. Start Ollama & Pull Models:**
```bash
.\scripts\pull_ollama_models.ps1
```

**5. Start Celery Worker (in separate terminal):**
```bash
conda activate rag_document_generator
celery -A workers.celery_app worker --loglevel=info
```

**6. Start Backend (in another terminal):**
```bash
.\scripts\start_backend.ps1
```

**7. Start Frontend (in another terminal):**
```bash
.\scripts\start_frontend.ps1
```

**8. Open Dashboard:**
```
http://localhost:8501
```

### Option 3: Docker Compose

```bash
docker-compose up -d
```

All services start automatically:
- FastAPI (port 8000)
- Streamlit (port 8501)
- Ollama (port 11434)
- Qdrant (port 6333)
- Redis (port 6379)
- PostgreSQL (port 5432)

---

## 📡 API Reference

### Base URL
```
http://localhost:8000
```

### Sync Endpoints (Original)

#### POST /upload
Upload and ingest a document.
```bash
curl -X POST http://localhost:8000/upload \
  -F "project_id=my_project" \
  -F "file=@document.pdf"
```

#### POST /generate
Generate a document.
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my_project",
    "title": "My Document",
    "prompt": "Generate a technical report"
  }'
```

### Async Endpoints (New)

#### POST /upload/async
Queue document ingestion asynchronously.

**Request:**
```bash
curl -X POST http://localhost:8000/upload/async \
  -F "project_id=my_project" \
  -F "file=@document.pdf"
```

**Response:**
```json
{
  "task_id": "abc123def456",
  "status": "pending",
  "message": "Document ingestion queued",
  "created_at": "2024-06-11T10:30:00Z"
}
```

#### POST /generate/async
Queue document generation asynchronously.

**Request:**
```bash
curl -X POST http://localhost:8000/generate/async \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my_project",
    "title": "Technical Report",
    "prompt": "Generate a comprehensive technical report",
    "required_sections": ["Introduction", "Architecture", "Conclusion"]
  }'
```

**Response:**
```json
{
  "task_id": "task_xyz789",
  "status": "pending",
  "message": "Document generation queued",
  "created_at": "2024-06-11T10:35:00Z"
}
```

#### GET /tasks/{task_id}/status
Get task progress and status.

**Request:**
```bash
curl http://localhost:8000/tasks/abc123def456/status
```

**Response:**
```json
{
  "task_id": "abc123def456",
  "status": "started",
  "progress": 35,
  "current": "Writing section 2 of 4",
  "result": null,
  "error": null,
  "started_at": "2024-06-11T10:30:15Z",
  "completed_at": null
}
```

**Status Values:** `pending`, `started`, `success`, `failure`, `revoked`

#### DELETE /tasks/{task_id}
Cancel a running task.

**Request:**
```bash
curl -X DELETE http://localhost:8000/tasks/abc123def456
```

**Response:**
```json
{
  "task_id": "abc123def456",
  "status": "revoked",
  "message": "Task cancellation requested"
}
```

### Export Endpoints (New)

#### POST /projects/{project_id}/export/{run_id}/pdf
Export generated document as PDF.

**Request:**
```bash
curl -X POST http://localhost:8000/projects/my_project/export/run_001/pdf \
  -o document.pdf
```

**Response:** Binary PDF file

### Streaming Endpoints (New)

#### WebSocket /ws/generation/{task_id}
Real-time generation progress updates.

**JavaScript Example:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/generation/task_id");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === "event") {
    const evt = data.event;
    console.log(`[${evt.progress}%] ${evt.message}`);
  }
};
```

**Python Example:**
```python
import asyncio
import websockets
import json

async def monitor(task_id):
    uri = f"ws://localhost:8000/ws/generation/{task_id}"
    async with websockets.connect(uri) as ws:
        async for message in ws:
            data = json.loads(message)
            if data["type"] == "event":
                print(f"Progress: {data['event']['progress']}%")

asyncio.run(monitor("task_id"))
```

**Event Types:**
- `generation.started` - Generation began
- `generation.section.planning` - Planning section
- `generation.section.writing` - Writing section
- `generation.section.validating` - Validating section
- `generation.section.completed` - Section done
- `generation.editing` - Final editing
- `generation.completed` - All done
- `generation.error` - Error occurred

#### GET /stream/{task_id}/history
Retrieve event history for a task.

```bash
curl http://localhost:8000/stream/task_id/history
```

**Response:**
```json
[
  {
    "type": "generation.started",
    "progress": 0,
    "message": "Starting generation",
    "timestamp": "2024-06-11T10:30:00Z"
  },
  ...
]
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file or set environment variables:

```bash
# API
API_PORT=8000
STREAMLIT_PORT=8501

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
GENERATION_MODEL=mistral          # or llama2, neural-chat, etc.
EMBEDDING_MODEL=nomic-embed-text

# Redis (for async support)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# Generation
GENERATION_TIMEOUT_SECONDS=3600
MAX_UPLOAD_MB=100

# Parallel Generation
MAX_CONCURRENT_SECTIONS=3

# Vector Storage
VECTOR_DB_TYPE=json               # or qdrant, postgres
```

### Configuration Methods

**1. Launcher Setup Wizard:**
```powershell
.\launch.ps1 -Config
```

**2. View Current Config:**
```powershell
.\launch.ps1 -ShowConfig
```

**3. Manual `.env` File:**
```bash
# Edit .env directly
nano .env
```

### Performance Tuning

| Setting | Impact | Recommended |
|---------|--------|-------------|
| `MAX_CONCURRENT_SECTIONS` | Parallel generation speed | 3-5 |
| `GENERATION_TIMEOUT_SECONDS` | Max time per generation | 3600 |
| `EMBEDDING_MODEL` | Accuracy vs speed | nomic-embed-text |
| `GENERATION_MODEL` | Quality vs speed | mistral |

---

## 🧪 Testing

### Run All Tests

**Using Launcher:**
```powershell
.\launch.ps1 -Test
```

**Direct Pytest:**
```bash
pytest tests/ -v
```

### Test Coverage

**Generate Coverage Report:**
```bash
pytest tests/ --cov=backend --cov-report=html
```

Open `htmlcov/index.html` in browser for detailed report.

### Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_generation.py` | 20 | Generation, validation, export |
| `test_api.py` | 25 | All API endpoints |
| `test_streaming_parallel.py` | 15+ | Async, streaming, parallel |

**Total:** 60+ test cases

### Running Specific Tests

```bash
# Test only generation
pytest tests/test_generation.py -v

# Test only APIs
pytest tests/test_api.py -v

# Test specific function
pytest tests/test_api.py::TestAsyncAPIs::test_generate_async -v

# Stop on first failure
pytest tests/ -v -x
```

---

## 🛠️ Troubleshooting

### Issue: Redis Connection Error

**Problem:** `Error: Could not connect to Redis at localhost:6379`

**Solutions:**
1. **Start Redis:**
   ```bash
   docker run -d -p 6379:6379 redis:latest
   ```

2. **Or install locally:**
   ```bash
   choco install redis -y
   redis-server
   ```

3. **Check Redis is running:**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

### Issue: Ollama Model Not Found

**Problem:** `Error: model 'mistral' not found`

**Solutions:**
1. **Pull models:**
   ```powershell
   .\scripts\pull_ollama_models.ps1
   ```

2. **Or manually:**
   ```bash
   ollama pull mistral
   ollama pull nomic-embed-text
   ```

3. **List available models:**
   ```bash
   ollama list
   ```

### Issue: Port Already in Use

**Problem:** `Address already in use: ('localhost', 8000)`

**Solutions:**
1. **Find process using port:**
   ```bash
   # On Windows
   netstat -ano | findstr :8000
   # Kill process (PID)
   taskkill /PID <PID> /F
   ```

2. **Or change port in `.env`:**
   ```bash
   API_PORT=8001
   ```

### Issue: Celery Worker Not Starting

**Problem:** `ModuleNotFoundError: No module named 'celery'`

**Solutions:**
1. **Reinstall requirements:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Activate conda environment:**
   ```bash
   conda activate rag_document_generator
   ```

3. **Start Celery with full path:**
   ```bash
   python -m celery -A workers.celery_app worker --loglevel=info
   ```

### Issue: WebSocket Connection Failed

**Problem:** `WebSocket connection error`

**Solutions:**
1. **Check backend is running:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check task exists:**
   ```bash
   curl http://localhost:8000/tasks/invalid_id/status
   ```

3. **Verify task_id is correct** - check task status first

### Issue: Tests Failing

**Problem:** `pytest: command not found`

**Solutions:**
1. **Install test dependencies:**
   ```bash
   pip install pytest pytest-asyncio pytest-cov
   ```

2. **Ensure Redis is running:**
   ```bash
   redis-cli ping
   ```

3. **Run with verbose output:**
   ```bash
   pytest tests/ -vv -s
   ```

---

## 📚 Command Line Tools

### Backup & Cleanup CLI

Located at `scripts/backup_cleanup_cli.py`

```bash
# Backup a project
python scripts/backup_cleanup_cli.py backup create my_project

# List backups
python scripts/backup_cleanup_cli.py backup list

# Restore from backup
python scripts/backup_cleanup_cli.py backup restore my_project /path/to/backup

# Cleanup old runs (30 days old)
python scripts/backup_cleanup_cli.py cleanup old-runs my_project --days 30

# Get storage statistics
python scripts/backup_cleanup_cli.py cleanup stats

# Archive project
python scripts/backup_cleanup_cli.py cleanup archive my_project

# Dry run (preview without changes)
python scripts/backup_cleanup_cli.py cleanup old-runs my_project --dry-run
```

---

## 📊 Project Structure

```
.
├── README.md                           # This file
├── IMPLEMENTATION_STATUS.md            # Feature status & summary
├── docker-compose.yml                  # Docker services
├── requirements.txt                    # Python dependencies
├── environment.yml                     # Conda environment
├── launch.ps1                          # Main launcher
│
├── backend/                            # FastAPI backend
│   ├── main.py
│   ├── health.py
│   ├── agents/                         # Agent implementations
│   ├── api/                            # API routes & models
│   ├── config/                         # Configuration
│   ├── exporters/                      # Export formats (DOCX, PDF)
│   ├── ingestion/                      # Document parsing & multimodal
│   ├── orchestration/                  # Workflow orchestration
│   ├── retrieval/                      # Vector search
│   ├── storage/                        # Data persistence
│   ├── streaming/                      # WebSocket events
│   └── templates/                      # DOCX templates
│
├── frontend/                           # Streamlit dashboard
│   └── streamlit_app/
│
├── workers/                            # Celery worker tasks
│   ├── celery_app.py
│   └── tasks.py
│
├── scripts/                            # Utility scripts
│   ├── launch.ps1
│   ├── pull_ollama_models.ps1
│   ├── start_backend.ps1
│   ├── start_frontend.ps1
│   └── backup_cleanup_cli.py
│
├── tests/                              # Test suites
│   ├── test_generation.py
│   ├── test_api.py
│   └── test_streaming_parallel.py
│
└── storage/                            # Data directory
    ├── projects/
    ├── vectors/
    ├── cache/
    └── templates/
```

---

## 🤝 Contributing

Contributions welcome! Areas for enhancement:

- [ ] PostgreSQL backend integration
- [ ] Qdrant vector store integration
- [ ] Authentication & authorization
- [ ] Rate limiting & quotas
- [ ] Advanced monitoring & metrics
- [ ] Custom agent development
- [ ] Model fine-tuning pipeline

---

## 📝 License

See LICENSE file for details.

---

## 🔗 Resources

- **Ollama:** https://ollama.ai
- **FastAPI:** https://fastapi.tiangolo.com
- **Streamlit:** https://streamlit.io
- **Celery:** https://docs.celeryproject.io
- **WebSockets:** https://websockets.readthedocs.io

---

## ✅ Status Summary

| Feature | Status | Version |
|---------|--------|---------|
| Document Ingestion | ✅ Complete | v1.0 |
| Vector Retrieval | ✅ Complete | v1.0 |
| Document Generation | ✅ Complete | v1.0 |
| Validation | ✅ Complete | v2.0 |
| DOCX Export | ✅ Complete | v1.0 |
| PDF Export | ✅ Complete | v2.0 |
| Async API | ✅ Complete | v2.0 |
| WebSocket Streaming | ✅ Complete | v2.0 |
| Parallel Generation | ✅ Complete | v2.0 |
| Backup/Cleanup | ✅ Complete | v2.0 |
| Test Suite | ✅ Complete | v2.0 |
| Dashboard UI | ✅ Complete | v1.0 |

**Latest Release:** v2.0 (June 11, 2026)  
**Next Steps:** Production deployment, monitoring setup

---

**Need help?** Check [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for detailed feature documentation.
