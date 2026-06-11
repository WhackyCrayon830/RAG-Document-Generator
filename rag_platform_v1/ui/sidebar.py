"""Sidebar component for Streamlit UI."""

import streamlit as st
from utils.helpers import (
    load_json_config,
    list_prompt_files,
    list_local_models,
)


def get_ollama_models(host="http://localhost:11434"):
    try:
        import ollama

        client = ollama.Client(host=host)

        response = client.list()

        models = []

        # New Ollama API
        if hasattr(response, "models"):
            for m in response.models:
                models.append(m.model)

        # Old API
        elif isinstance(response, dict):
            models = [
                m.get("name") or m.get("model")
                for m in response.get("models", [])
            ]

        return [m for m in models if m]

    except Exception as e:
        print("OLLAMA ERROR:", e)
        return []


def render_sidebar() -> dict:
    """
    Render the sidebar and return settings.
    """

    cfg = load_json_config("config/models_config.json")

    online_models = cfg.get(
        "online_models",
        [],
    )

    offline_models = list_local_models("models")

    embedding_models = cfg.get(
        "embedding_models",
        ["sentence-transformers/all-MiniLM-L6-v2"],
    )

    prompt_files = list_prompt_files("prompts")

    st.sidebar.title("⚙️ RAG Platform")
    st.sidebar.markdown("---")

    # =====================================================
    # Inference Mode
    # =====================================================

    mode = st.sidebar.radio(
        "Inference Mode",
        [
            "🖥️ Offline (Local)",
            "🌐 Online (HuggingFace)",
            "🦙 Ollama",
        ],
        key="inference_mode",
    )

    is_online = "Online" in mode

    is_ollama = "Ollama" in mode

    hf_token = ""

    ollama_host = "http://localhost:11434"

    ollama_model = ""

    # =====================================================
    # HuggingFace
    # =====================================================

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

    # =====================================================
    # Model Selection
    # =====================================================

    st.sidebar.markdown("#### 🤖 Model")

    if is_online:

        model_options = online_models if online_models else ["Qwen/Qwen2.5-3B-Instruct"]

        selected_model = st.sidebar.selectbox(
            "Online Model",
            model_options,
            key="online_model",
        )

    elif is_ollama:

        ollama_host = st.sidebar.text_input(
            "Ollama Host",
            value="http://localhost:11434",
            key="ollama_host",
        )

        ollama_models = get_ollama_models(ollama_host)

        if not ollama_models:

            st.sidebar.warning(
                "No Ollama models detected.\n\n" "Example:\n" "ollama pull gemma3:4b"
            )

            selected_model = ""

        else:

            ollama_model = st.sidebar.selectbox(
                "Ollama Model",
                ollama_models,
                key="ollama_model",
            )

            selected_model = ollama_model

    else:

        if not offline_models:

            st.sidebar.error(
                "❌ No local models found in models/\n\n"
                "Download a model and place it in the models directory.\n"
                "Example: models/phi-3-mini/"
            )

            selected_model = ""

        else:

            selected_model = st.sidebar.selectbox(
                "Local Model",
                offline_models,
                key="local_model",
            )

    # =====================================================
    # Embeddings
    # =====================================================

    st.sidebar.markdown("#### 📐 Embedding Model")

    selected_embedding = st.sidebar.selectbox(
        "Embedding Model",
        embedding_models,
        key="embedding_model",
    )

    # =====================================================
    # App Mode
    # =====================================================

    st.sidebar.markdown("#### 🎯 App Mode")

    app_mode = st.sidebar.selectbox(
        "Mode",
        [
            "💬 Chatbot",
            "📄 Documentation Generator",
        ],
        key="app_mode",
    )

    # =====================================================
    # Prompt
    # =====================================================

    st.sidebar.markdown("#### 📝 System Prompt")

    if prompt_files:

        selected_prompt = st.sidebar.selectbox(
            "Prompt File",
            prompt_files,
            key="prompt_file",
        )

    else:

        selected_prompt = ""

        st.sidebar.info("No prompt files in prompts/ folder.")

    # =====================================================
    # Retrieval
    # =====================================================

    st.sidebar.markdown("#### 🔍 Retrieval Settings")

    top_k = st.sidebar.slider(
        "Top-K chunks",
        min_value=1,
        max_value=15,
        value=5,
        key="top_k",
    )

    max_tokens = st.sidebar.slider(
        "Max new tokens",
        min_value=128,
        max_value=2048,
        value=512,
        step=64,
        key="max_tokens",
    )

    # =====================================================
    # Vector DB
    # =====================================================

    st.sidebar.markdown("#### 🗄️ Vector Database")

    col1, col2 = st.sidebar.columns(2)

    rebuild_db = col1.button(
        "🔄 Rebuild DB",
        key="rebuild_db_btn",
    )

    clear_chat = col2.button(
        "🗑️ Clear Chat",
        key="clear_chat_btn",
    )

    st.sidebar.markdown("---")

    # =====================================================
    # Return Settings
    # =====================================================

    return {
        "provider": ("ollama" if is_ollama else ("online" if is_online else "offline")),
        "is_online": is_online,
        "is_ollama": is_ollama,
        "hf_token": hf_token,
        "selected_model": selected_model,
        "ollama_model": ollama_model,
        "ollama_host": ollama_host,
        "selected_embedding": selected_embedding,
        "app_mode": app_mode,
        "selected_prompt": selected_prompt,
        "top_k": top_k,
        "max_tokens": max_tokens,
        "rebuild_db": rebuild_db,
        "clear_chat": clear_chat,
    }
