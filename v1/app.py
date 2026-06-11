"""
RAG Platform - Main Streamlit Application
Production-grade modular RAG with offline/online support.
"""
import os
import sys
import tempfile
import logging
import streamlit as st

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Session state initialisation (must be first Streamlit call) ──────────────
def _init_session_state():
    defaults = {
        "messages": [],
        "log_lines": [],
        "vs_ready": False,
        "llm_ready": False,
        "plugins_ready": False,
        "ingestion_done": False,
        "rag_chain": None,
        "doc_generator": None,
        "vector_store": None,
        "llm_manager": None,
        "hw_info": None,
        "last_model": "",
        "last_embedding": "",
        "generated_doc": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session_state()

# ── Logging setup ─────────────────────────────────────────────────────────────
from utils.logger import setup_logging
setup_logging(st.session_state["log_lines"])
logger = logging.getLogger("rag_platform")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Platform",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Imports ───────────────────────────────────────────────────────────────────
from ui.sidebar import render_sidebar
from ui.chat_interface import render_chat_history, render_ingestion_uploader
from ui.components import render_status_panel, render_debug_panel, render_source_badges
from ingestion.plugin_registry import registry
from ingestion.ingestion_engine import IngestionEngine
from retrieval.vector_store import VectorStore
from retrieval.retriever import Retriever
from generation.llm_manager import LLMManager
from generation.rag_chain import RAGChain
from generation.doc_generator import DocGenerator
from services.hardware_detector import get_hardware_info
from services.export_service import export_to_html, export_to_docx, export_to_pdf
from utils.helpers import load_prompt_file, list_prompt_files


# ── Plugin loading ────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_plugins():
    registry.discover_and_load()
    return registry


@st.cache_resource(show_spinner=False)
def load_hardware():
    return get_hardware_info()


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_or_create_vector_store(embedding_model: str) -> VectorStore:
    """Return existing vs or create new one if model changed."""
    if (
        st.session_state["vector_store"] is None
        or st.session_state["last_embedding"] != embedding_model
    ):
        vs = VectorStore(embedding_model_name=embedding_model)
        vs.load()
        st.session_state["vector_store"] = vs
        st.session_state["last_embedding"] = embedding_model
        logger.info(f"Vector store initialised with {vs.chunk_count} chunks.")
    return st.session_state["vector_store"]


def get_or_create_llm(settings: dict) -> LLMManager:
    """Return existing LLM or load new one if model changed."""
    model_key = settings["selected_model"]
    if (
        st.session_state["llm_manager"] is None
        or not st.session_state["llm_manager"].is_loaded
        or st.session_state["last_model"] != model_key
    ):
        llm = LLMManager()
        if settings["is_online"]:
            ok = llm.load_online(settings["selected_model"], settings["hf_token"])
        else:
            model_path = os.path.join("models", settings["selected_model"])
            ok = llm.load_offline(model_path)

        if ok:
            st.session_state["llm_manager"] = llm
            st.session_state["last_model"] = model_key
            st.session_state["llm_ready"] = True
            logger.info(f"LLM loaded: {model_key}")
        else:
            st.session_state["llm_ready"] = False
            logger.error(f"LLM load failed: {model_key}")

    return st.session_state["llm_manager"]


def save_uploaded_file(uploaded_file) -> str:
    """Save Streamlit uploaded file to temp directory, return path."""
    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix=uploaded_file.name + "_") as tmp:
        tmp.write(uploaded_file.read())
        return tmp.name


# ── Main App ──────────────────────────────────────────────────────────────────
def main():
    # Load plugins and hardware once
    reg = load_plugins()
    hw_info = load_hardware()
    st.session_state["hw_info"] = hw_info

    # Sidebar
    settings = render_sidebar()

    # Get components
    vs = get_or_create_vector_store(settings["selected_embedding"])
    llm = None

    # ── Status Panel ─────────────────────────────────────────────────────────
    render_status_panel(
        hw_info=hw_info,
        vs_chunk_count=vs.chunk_count,
        llm_loaded=st.session_state["llm_ready"],
        llm_mode="online" if settings["is_online"] else "offline",
        llm_model=st.session_state["last_model"],
        plugins_loaded=reg.get_loaded_plugins(),
        plugin_errors=reg.get_load_errors(),
    )

    # ── Rebuild DB ────────────────────────────────────────────────────────────
    if settings.get("rebuild_db"):
        with st.spinner("Rebuilding vector database..."):
            vs.clear()
            vs.save()
            st.session_state["rag_chain"] = None
            st.success("✅ Vector database cleared. Re-ingest your documents.")
        st.rerun()

    # ── Clear Chat ────────────────────────────────────────────────────────────
    if settings.get("clear_chat"):
        st.session_state["messages"] = []
        if st.session_state.get("rag_chain"):
            st.session_state["rag_chain"].clear_history()
        st.rerun()

    # ── Document Upload & Ingestion ───────────────────────────────────────────
    with st.expander("📂 Upload & Ingest Documents", expanded=not vs.is_ready):
        uploaded_files = render_ingestion_uploader()

        if uploaded_files:
            if st.button("⚡ Ingest Selected Files", key="ingest_btn"):
                engine = IngestionEngine()
                progress_placeholder = st.empty()
                progress_bar = st.progress(0)
                all_chunks = []

                for i, uploaded_file in enumerate(uploaded_files):
                    tmp_path = save_uploaded_file(uploaded_file)
                    log_msgs = []

                    def prog_cb(msg, _path=tmp_path):
                        log_msgs.append(msg)
                        progress_placeholder.info(msg)

                    chunks = engine.ingest_file(tmp_path, progress_cb=prog_cb)
                    all_chunks.extend(chunks)
                    progress_bar.progress((i + 1) / len(uploaded_files))

                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                if all_chunks:
                    with st.spinner(f"Embedding {len(all_chunks)} chunks..."):
                        vs.add_chunks(all_chunks)
                        vs.save()
                    st.success(f"✅ Ingested {len(all_chunks)} chunks from {len(uploaded_files)} file(s).")
                    st.session_state["rag_chain"] = None  # Reset chain to use updated VS
                    st.rerun()
                else:
                    st.warning("No chunks extracted. Check file format and plugin support.")

    # ── Load LLM Button ───────────────────────────────────────────────────────
    if not st.session_state["llm_ready"]:
        if settings["is_online"] and not settings["hf_token"]:
            st.warning("⚠️ Enter your HuggingFace token in the sidebar to use online mode.")
        elif not settings["selected_model"]:
            st.error("❌ No model selected. Add a local model to the `models/` folder.")
        else:
            if st.button(f"🚀 Load Model: {settings['selected_model']}", key="load_model_btn"):
                with st.spinner("Loading model... (this may take a moment)"):
                    llm = get_or_create_llm(settings)
                if st.session_state["llm_ready"]:
                    st.success(f"✅ Model loaded: {settings['selected_model']}")
                    st.rerun()
                else:
                    st.error("❌ Model load failed. Check logs below.")
    else:
        llm = st.session_state["llm_manager"]

    # ── App Modes ─────────────────────────────────────────────────────────────
    app_mode = settings.get("app_mode", "💬 Chatbot")

    if "Chatbot" in app_mode:
        _render_chat_mode(settings, vs, llm)
    else:
        _render_doc_gen_mode(settings, vs, llm)

    # ── Debug Panel ───────────────────────────────────────────────────────────
    render_debug_panel(st.session_state["log_lines"])


# ── Chat Mode ─────────────────────────────────────────────────────────────────
def _render_chat_mode(settings: dict, vs: VectorStore, llm):
    st.markdown("## 💬 Technical Assistant")

    if not vs.is_ready:
        st.info("📂 Please ingest documents above to enable retrieval-augmented answers.")

    # Render history
    render_chat_history(st.session_state["messages"])

    # Chat input
    query = st.chat_input("Ask a question about your documents...")
    if not query:
        return

    if not st.session_state["llm_ready"] or llm is None:
        st.warning("⚠️ Please load a model first.")
        return

    # Add user message
    st.session_state["messages"].append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    # Load prompt
    system_prompt = ""
    if settings.get("selected_prompt"):
        system_prompt = load_prompt_file(os.path.join("prompts", settings["selected_prompt"]))

    # Build or reuse RAG chain
    if st.session_state["rag_chain"] is None or True:  # Always rebuild with current settings
        retriever = Retriever(vs, top_k=settings["top_k"])
        st.session_state["rag_chain"] = RAGChain(
            retriever=retriever,
            llm_manager=llm,
            system_prompt=system_prompt,
        )

    chain: RAGChain = st.session_state["rag_chain"]

    # Stream response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        source_chunks = []

        try:
            for event in chain.query(
                query,
                top_k=settings["top_k"],
                stream=True,
                max_new_tokens=settings["max_tokens"],
            ):
                if event["type"] == "sources":
                    source_chunks = event["data"]
                    if source_chunks:
                        render_source_badges(source_chunks)
                elif event["type"] == "token":
                    full_response += event["data"]
                    response_placeholder.markdown(full_response + "▌")
                elif event["type"] == "done":
                    response_placeholder.markdown(full_response)
                elif event["type"] == "error":
                    st.error(f"Generation error: {event['data']}")
                    return

        except Exception as e:
            st.error(f"❌ Error: {e}")
            logger.error(f"Chat error: {e}")
            return

    # Store message with sources
    src_meta = [
        {
            "text": c.text,
            "source": c.source,
            "page": c.page,
            "section": c.section,
            "confidence": c.confidence,
        }
        for c in source_chunks
    ]
    st.session_state["messages"].append({
        "role": "assistant",
        "content": full_response,
        "sources": src_meta,
    })


# ── Doc Generation Mode ───────────────────────────────────────────────────────
def _render_doc_gen_mode(settings: dict, vs: VectorStore, llm):
    st.markdown("## 📄 Documentation Generator")

    if not vs.is_ready:
        st.info("📂 Please ingest documents above before generating documentation.")
        return

    topic = st.text_input(
        "📝 Documentation Topic",
        placeholder="e.g. 'Installation procedure for pump XYZ-200'",
        key="doc_topic",
    )

    if st.button("✨ Generate Documentation", key="gen_doc_btn"):
        if not topic:
            st.warning("Please enter a topic.")
            return
        if not st.session_state["llm_ready"] or llm is None:
            st.warning("⚠️ Please load a model first.")
            return

        custom_prompt = ""
        if settings.get("selected_prompt"):
            custom_prompt = load_prompt_file(os.path.join("prompts", settings["selected_prompt"]))

        retriever = Retriever(vs, top_k=settings["top_k"])
        gen = DocGenerator(retriever=retriever, llm_manager=llm)

        doc_placeholder = st.empty()
        full_doc = ""

        with st.spinner("Generating documentation..."):
            try:
                for token in gen.generate(
                    topic=topic,
                    top_k=settings["top_k"],
                    max_new_tokens=settings["max_tokens"],
                    custom_prompt=custom_prompt,
                ):
                    full_doc += token
                    doc_placeholder.markdown(full_doc + "▌")
                doc_placeholder.markdown(full_doc)
                st.session_state["generated_doc"] = full_doc
            except Exception as e:
                st.error(f"Generation error: {e}")
                return

    # Show generated doc and export options
    if st.session_state.get("generated_doc"):
        doc = st.session_state["generated_doc"]
        st.markdown("---")
        st.markdown("### 📥 Export Options")
        col1, col2, col3 = st.columns(3)

        if col1.button("📄 Export HTML", key="exp_html"):
            out = "exports/generated_doc.html"
            os.makedirs("exports", exist_ok=True)
            if export_to_html(doc, out):
                with open(out, "rb") as f:
                    st.download_button("⬇️ Download HTML", f, "documentation.html", "text/html")

        if col2.button("📝 Export DOCX", key="exp_docx"):
            out = "exports/generated_doc.docx"
            os.makedirs("exports", exist_ok=True)
            if export_to_docx(doc, out):
                with open(out, "rb") as f:
                    st.download_button("⬇️ Download DOCX", f, "documentation.docx",
                                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        if col3.button("📋 Export PDF", key="exp_pdf"):
            out = "exports/generated_doc.pdf"
            os.makedirs("exports", exist_ok=True)
            if export_to_pdf(doc, out):
                with open(out, "rb") as f:
                    st.download_button("⬇️ Download PDF", f, "documentation.pdf", "application/pdf")
            else:
                st.warning("PDF export requires weasyprint or reportlab. Install one to enable PDF export.")


if __name__ == "__main__":
    main()
