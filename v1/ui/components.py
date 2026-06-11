"""Reusable UI components - status indicators, debug panels, etc."""
import streamlit as st
from typing import List, Dict, Any


def render_status_panel(
    hw_info,
    vs_chunk_count: int,
    llm_loaded: bool,
    llm_mode: str,
    llm_model: str,
    plugins_loaded: List[str],
    plugin_errors: Dict[str, str],
):
    """Render a status overview panel."""
    with st.expander("🔧 System Status", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**🖥️ Hardware**")
            if hw_info.has_cuda:
                st.success(f"GPU: {hw_info.gpu_name}\n{hw_info.gpu_memory_gb:.1f} GB VRAM")
            else:
                st.info(f"CPU Mode | {hw_info.cpu_cores} cores")

        with col2:
            st.markdown("**🤖 Model**")
            if llm_loaded:
                st.success(f"✅ Loaded ({llm_mode})\n`{llm_model}`")
            else:
                st.warning("⚠️ Not loaded")

        with col3:
            st.markdown("**🗄️ Vector DB**")
            if vs_chunk_count > 0:
                st.success(f"✅ {vs_chunk_count} chunks")
            else:
                st.warning("⚠️ Empty - ingest docs")

        st.markdown("**🔌 Loaded Plugins**")
        if plugins_loaded:
            st.code(", ".join(plugins_loaded))
        else:
            st.warning("No plugins loaded")

        if plugin_errors:
            st.markdown("**❌ Plugin Errors**")
            for name, err in plugin_errors.items():
                st.error(f"{name}: {err}")


def render_debug_panel(log_lines: List[str]):
    """Render scrollable debug log panel."""
    with st.expander("🪲 Debug Logs", expanded=False):
        if log_lines:
            st.code("\n".join(log_lines[-100:]), language="text")
        else:
            st.info("No logs yet.")


def render_source_badges(chunks):
    """Render small colored source badges."""
    if not chunks:
        return
    for c in chunks:
        color = {"high": "green", "medium": "orange", "low": "red"}.get(c.confidence, "gray")
        st.markdown(
            f'<span style="background:{color};color:white;padding:2px 8px;'
            f'border-radius:12px;font-size:0.75em;margin:2px">'
            f'📄 {c.source} {f"p.{c.page}" if c.page else ""}</span>',
            unsafe_allow_html=True,
        )
