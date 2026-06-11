# 🧠 RAG Platform

A production-grade modular Retrieval-Augmented Generation (RAG) platform with a Streamlit frontend.
Supports **fully offline** local model execution and optional **online HuggingFace inference**.

---

## ✨ Features

- **Modular plugin architecture** — add new file types by dropping a plugin file in `plugins/`
- **Supported formats:** PDF, DOCX, Markdown, TXT, CSV, XLSX, HTML
- **FAISS vector database** — persistent, incremental indexing
- **CPU-first design** — auto GPU acceleration if CUDA available
- **Two modes:** Chatbot with citations / Markdown documentation generator
- **Offline + Online** — local models or HuggingFace Inference API
- **Export:** HTML, DOCX, PDF

---

## 🚀 Quick Start

### Option 1: Conda (Recommended)

**Linux/macOS:**
```bash
bash setup_linux.sh
conda activate rag_platform
bash start.sh
```

**Windows:**
```
Double-click: setup_windows.bat
Then: start.bat
```

### Option 2: pip
```bash
pip install -r requirements.txt
streamlit run app.py
```

### Option 3: Docker
```bash
docker-compose up --build
```

---

## 📁 Project Structure

```
rag_platform/
├── app.py                     # Main Streamlit app
├── plugins/                   # File processor plugins (one per format)
│   ├── base_plugin.py         # Abstract base class
│   ├── pdf_plugin.py
│   ├── docx_plugin.py
│   ├── markdown_plugin.py
│   ├── txt_plugin.py
│   ├── csv_plugin.py
│   ├── xlsx_plugin.py
│   └── html_plugin.py
├── ingestion/
│   ├── plugin_registry.py     # Auto-discovers plugins
│   ├── ingestion_engine.py    # Orchestrates ingestion
│   └── chunker.py             # Recursive/token-aware chunking
├── retrieval/
│   ├── vector_store.py        # FAISS store with persistence
│   └── retriever.py           # Similarity search + confidence scoring
├── generation/
│   ├── llm_manager.py         # Local + online LLM loading
│   ├── rag_chain.py           # RAG query pipeline
│   └── doc_generator.py       # Markdown documentation generator
├── services/
│   ├── hardware_detector.py   # CPU/GPU auto-detection
│   └── export_service.py      # HTML/DOCX/PDF export
├── ui/
│   ├── sidebar.py             # Sidebar controls
│   ├── chat_interface.py      # Chat history and input
│   └── components.py          # Status panels, debug logs
├── utils/
│   ├── logger.py              # Structured logging
│   └── helpers.py             # Utility functions
├── config/
│   ├── models_config.json     # Model registry
│   └── app_config.json        # App settings
├── prompts/                   # System prompt templates
├── models/                    # Local model files (git-ignored)
├── vector_db/                 # FAISS index files (git-ignored)
└── exports/                   # Generated document exports
```

---

## 🔧 Configuration

### Offline Mode (Local Models)

1. Download a model into `models/<model-name>/`:
```bash
huggingface-cli download microsoft/Phi-3-mini-4k-instruct \
  --local-dir models/Phi-3-mini-4k-instruct
```

2. Select it in the sidebar → Offline mode → Local Model dropdown

**Recommended CPU models:**
| Model | Size | Speed |
|-------|------|-------|
| Phi-3-mini-4k-instruct | ~2.3GB | Fast |
| Qwen2.5-1.5B-Instruct | ~1.0GB | Very Fast |
| TinyLlama-1.1B | ~0.6GB | Fastest |

### Online Mode (HuggingFace)

1. Get a token at https://huggingface.co/settings/tokens
2. Add to `.env`: `HUGGINGFACE_TOKEN=hf_...`
3. Or enter directly in the sidebar
4. Select any model from the dropdown

---

## 🔌 Adding New File Type Plugins

1. Create `plugins/myformat_plugin.py`
2. Inherit from `BasePlugin`
3. Set `SUPPORTED_EXTENSIONS = [".myformat"]`
4. Implement `extract(file_path) -> List[DocumentChunk]`

That's it — the plugin is auto-discovered on next startup. No other changes needed.

**Example:**
```python
from plugins.base_plugin import BasePlugin, DocumentChunk

class MyFormatPlugin(BasePlugin):
    SUPPORTED_EXTENSIONS = [".myf"]

    def extract(self, file_path: str):
        # parse file, return list of DocumentChunk
        return [DocumentChunk(text="...", source=file_path, page=1)]
```

---

## 🛠️ Utility Scripts

```bash
# Validate all plugins
python validate_plugins.py

# Rebuild index from a folder
python rebuild_index.py --folder /path/to/docs

# Rebuild with custom settings
python rebuild_index.py --folder docs/ --chunk-size 256 --chunk-overlap 32
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "No local models found" | Download a model into `models/` subfolder |
| FAISS import error | `pip install faiss-cpu` |
| PyMuPDF error | `pip install pymupdf` |
| "Token required" | Add HF token to `.env` or sidebar |
| Slow responses | Use smaller model, reduce max tokens, or enable GPU |
| Import errors | Run `setup_linux.sh` or `setup_windows.bat` |

---

## 📄 License

MIT License - see LICENSE file for details.
