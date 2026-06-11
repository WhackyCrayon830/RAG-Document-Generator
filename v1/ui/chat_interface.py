"""Chat interface UI component."""
import streamlit as st
from typing import List


def render_chat_history(messages: List[dict]):
    """Render all chat messages in the history."""
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        sources = msg.get("sources", [])

        with st.chat_message(role):
            st.markdown(content)
            if sources:
                with st.expander(f"📚 Sources ({len(sources)})"):
                    for i, src in enumerate(sources, 1):
                        confidence_color = {
                            "high": "🟢",
                            "medium": "🟡",
                            "low": "🔴",
                        }.get(src.get("confidence", "low"), "⚪")
                        st.markdown(
                            f"**{confidence_color} Source {i}:** `{src.get('source', 'unknown')}`"
                            f" | Page: {src.get('page', 0)}"
                            f" | Section: {src.get('section', '-')}"
                        )
                        st.caption(src.get("text", "")[:300] + "...")


def render_typing_indicator():
    """Show a 'thinking' placeholder."""
    return st.empty()


def render_ingestion_uploader():
    """File upload widget for document ingestion."""
    st.markdown("### 📂 Ingest Documents")
    uploaded_files = st.file_uploader(
        "Upload files (PDF, DOCX, MD, TXT, CSV, XLSX, HTML)",
        accept_multiple_files=True,
        type=["pdf", "docx", "md", "txt", "csv", "xlsx", "html", "htm"],
        key="doc_uploader",
    )
    return uploaded_files
