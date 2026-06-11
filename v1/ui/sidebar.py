"""Sidebar component for Streamlit UI."""
import os
import streamlit as st
from utils.helpers import load_json_config, list_prompt_files, list_local_models


def render_sidebar() -> dict:
    """
    Render the sidebar and return a dict with all selected settings.
    Uses session_state to persist values across reruns.
    """
    cfg = load_json_config("config/models_config.json")
    online_models = cfg.get("online_models", [])
    offline_models = list_local_models("models")
    embedding_models = cfg.get("embedding_models", ["sentence-transformers/all-MiniLM-L6-v2"])
    prompt_files = list_prompt_files("prompts")

    st.sidebar.title("⚙️ RAG Platform")
    st.sidebar.markdown("---")

    # --- Mode toggle ---
    mode = st.sidebar.radio(
        "Inference Mode",
        ["🖥️ Offline (Local)", "🌐 Online (HuggingFace)"],
        key="inference_mode",
    )
    is_online = "Online" in mode

    # --- HF Token ---
    hf_token = ""
    if is_online:
        st.sidebar.markdown("#### 🔑 HuggingFace Token")
        hf_token = st.sidebar.text_input(
            "HF Token",
            type="password",
            key="hf_token",
            help="Required for online inference mode",
        )
        if not hf_token:
            st.sidebar.warning("⚠️ Token required for online mode.")

    # --- Model selection ---
    st.sidebar.markdown("#### 🤖 Model")
    if is_online:
        model_options = online_models if online_models else ["Qwen/Qwen2.5-3B-Instruct"]
        selected_model = st.sidebar.selectbox("Online Model", model_options, key="online_model")
    else:
        if not offline_models:
            st.sidebar.error(
                "❌ No local models found in models/\n\n"
                "Download a model and place it in the `models/` directory.\n"
                "Example: `models/phi-3-mini/`"
            )
            selected_model = ""
        else:
            selected_model = st.sidebar.selectbox("Local Model", offline_models, key="local_model")

    # --- Embedding model ---
    st.sidebar.markdown("#### 📐 Embedding Model")
    selected_embedding = st.sidebar.selectbox(
        "Embedding Model",
        embedding_models,
        key="embedding_model",
    )

    # --- App mode ---
    st.sidebar.markdown("#### 🎯 App Mode")
    app_mode = st.sidebar.selectbox(
        "Mode",
        ["💬 Chatbot", "📄 Documentation Generator"],
        key="app_mode",
    )

    # --- Prompt file ---
    st.sidebar.markdown("#### 📝 System Prompt")
    if prompt_files:
        selected_prompt = st.sidebar.selectbox("Prompt File", prompt_files, key="prompt_file")
    else:
        selected_prompt = ""
        st.sidebar.info("No prompt files in prompts/ folder.")

    # --- Retrieval settings ---
    st.sidebar.markdown("#### 🔍 Retrieval Settings")
    top_k = st.sidebar.slider("Top-K chunks", min_value=1, max_value=15, value=5, key="top_k")
    max_tokens = st.sidebar.slider("Max new tokens", min_value=128, max_value=2048, value=512, step=64, key="max_tokens")

    # --- Vector DB actions ---
    st.sidebar.markdown("#### 🗄️ Vector Database")
    col1, col2 = st.sidebar.columns(2)
    rebuild_db = col1.button("🔄 Rebuild DB", key="rebuild_db_btn")
    clear_chat = col2.button("🗑️ Clear Chat", key="clear_chat_btn")

    st.sidebar.markdown("---")

    return {
        "is_online": is_online,
        "hf_token": hf_token,
        "selected_model": selected_model,
        "selected_embedding": selected_embedding,
        "app_mode": app_mode,
        "selected_prompt": selected_prompt,
        "top_k": top_k,
        "max_tokens": max_tokens,
        "rebuild_db": rebuild_db,
        "clear_chat": clear_chat,
    }
