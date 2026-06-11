import os
import time
from pathlib import Path

import requests
import streamlit as st


DEFAULT_API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


st.set_page_config(page_title="RAG Document Generator", layout="wide", initial_sidebar_state="collapsed")


def init_state() -> None:
    defaults = {
        "api_url": DEFAULT_API_URL,
        "dark_mode": True,
        "active_project_id": None,
        "last_result": None,
        "workflow_steps": {
            "Clarification": "Waiting",
            "Planner": "Waiting",
            "Retriever": "Waiting",
            "Writer": "Waiting",
            "Validator": "Waiting",
            "Editor": "Waiting",
            "DOCX Export": "Waiting",
        },
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


init_state()


def inject_css(dark_mode: bool) -> None:
    if dark_mode:
        colors = {
            "bg": "#0f1117",
            "panel": "#171b24",
            "panel_2": "#202634",
            "text": "#f2f4f8",
            "muted": "#9aa4b2",
            "border": "#2d3545",
            "accent": "#5dd6c7",
            "ok": "#64d887",
            "warn": "#f2c66d",
        }
    else:
        colors = {
            "bg": "#f6f7fb",
            "panel": "#ffffff",
            "panel_2": "#eef2f7",
            "text": "#161a22",
            "muted": "#627084",
            "border": "#d9e0ea",
            "accent": "#176b87",
            "ok": "#207a45",
            "warn": "#9b6417",
        }

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {colors["bg"]};
            color: {colors["text"]};
        }}
        [data-testid="stHeader"] {{
            background: transparent;
        }}
        .main .block-container {{
            max-width: 1320px;
            padding-top: 2rem;
        }}
        .app-title {{
            font-size: 2.1rem;
            font-weight: 760;
            letter-spacing: 0;
            margin-bottom: .2rem;
        }}
        .app-subtitle {{
            color: {colors["muted"]};
            font-size: 1rem;
            margin-bottom: 1.2rem;
        }}
        .metric-card, .agent-card, .soft-card {{
            background: {colors["panel"]};
            border: 1px solid {colors["border"]};
            border-radius: 14px;
            padding: 1rem;
            box-shadow: 0 10px 30px rgba(0,0,0,.08);
        }}
        .agent-card {{
            position: sticky;
            top: 1rem;
        }}
        .card-title {{
            font-size: 1.02rem;
            font-weight: 720;
            margin-bottom: .75rem;
        }}
        .step-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: .75rem;
            border-bottom: 1px solid {colors["border"]};
            padding: .62rem 0;
        }}
        .step-row:last-child {{
            border-bottom: 0;
        }}
        .step-name {{
            color: {colors["text"]};
            font-weight: 620;
        }}
        .pill {{
            border-radius: 999px;
            padding: .2rem .55rem;
            font-size: .78rem;
            white-space: nowrap;
            background: {colors["panel_2"]};
            color: {colors["muted"]};
            border: 1px solid {colors["border"]};
        }}
        .pill-done {{
            color: {colors["ok"]};
            border-color: {colors["ok"]};
        }}
        .pill-active {{
            color: {colors["accent"]};
            border-color: {colors["accent"]};
        }}
        .pill-review {{
            color: {colors["warn"]};
            border-color: {colors["warn"]};
        }}
        .small-muted {{
            color: {colors["muted"]};
            font-size: .9rem;
        }}
        div[data-testid="stTabs"] button {{
            border-radius: 999px;
        }}
        div.stButton > button, div[data-testid="stDownloadButton"] button {{
            border-radius: 10px;
            font-weight: 650;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def api_get(path: str):
    response = requests.get(f"{st.session_state.api_url}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def api_post(path: str, json=None, files=None, data=None):
    response = requests.post(
        f"{st.session_state.api_url}{path}",
        json=json,
        files=files,
        data=data,
        timeout=600,
    )
    response.raise_for_status()
    return response.json()


def render_header() -> None:
    left, right = st.columns([3, 1])
    with left:
        st.markdown('<div class="app-title">Offline RAG Document Generator</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="app-subtitle">Generate template-aware documents with local Ollama agents and scoped retrieval.</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.session_state.api_url = st.text_input("Backend", value=st.session_state.api_url, label_visibility="collapsed")


def status_pill(status: str) -> str:
    css = "pill"
    if status == "Complete":
        css += " pill-done"
    elif status == "Running":
        css += " pill-active"
    elif status == "Review":
        css += " pill-review"
    return f'<span class="{css}">{status}</span>'


def render_agent_card() -> None:
    rows = []
    for name, status in st.session_state.workflow_steps.items():
        rows.append(
            f"""
            <div class="step-row">
                <span class="step-name">{name}</span>
                {status_pill(status)}
            </div>
            """
        )
    st.markdown(
        f"""
        <div class="agent-card">
            <div class="card-title">Agent workflow</div>
            {''.join(rows)}
            <div class="small-muted" style="margin-top:.75rem;">
                Writers only receive the current section, adjacent summaries, template hints, and retrieved evidence.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def set_workflow(active: str | None = None, done: list[str] | None = None, review: list[str] | None = None) -> None:
    done = done or []
    review = review or []
    for step in st.session_state.workflow_steps:
        if step in done:
            st.session_state.workflow_steps[step] = "Complete"
        elif step in review:
            st.session_state.workflow_steps[step] = "Review"
        elif step == active:
            st.session_state.workflow_steps[step] = "Running"
        else:
            st.session_state.workflow_steps[step] = "Waiting"


def load_projects() -> list[dict]:
    try:
        return api_get("/projects")
    except requests.RequestException:
        return []


def selected_project(projects: list[dict]) -> dict | None:
    if not projects:
        return None
    ids = [project["id"] for project in projects]
    if st.session_state.active_project_id not in ids:
        st.session_state.active_project_id = ids[0]
    for project in projects:
        if project["id"] == st.session_state.active_project_id:
            try:
                return api_get(f"/projects/{project['id']}")
            except requests.RequestException:
                return project
    return projects[0]


def render_project_picker(projects: list[dict]) -> None:
    with st.sidebar:
        st.markdown("### Workspace")
        if projects:
            labels = {f"{project['name']} · {project['id'][:8]}": project["id"] for project in projects}
            current_label = next(
                (label for label, pid in labels.items() if pid == st.session_state.active_project_id),
                list(labels.keys())[0],
            )
            choice = st.selectbox("Project", list(labels.keys()), index=list(labels.keys()).index(current_label))
            st.session_state.active_project_id = labels[choice]
        with st.form("create_project"):
            name = st.text_input("New project")
            if st.form_submit_button("Create project") and name.strip():
                project = api_post("/projects", json={"name": name.strip()})
                st.session_state.active_project_id = project["id"]
                st.rerun()


def get_model_settings() -> dict:
    try:
        return api_get("/settings/models")
    except requests.RequestException:
        return {
            "embedding_model": "nomic-embed-text",
            "planning_model": "qwen3:14b",
            "writing_model": "qwen3:14b",
            "validation_model": "gemma3:12b",
            "editing_model": "mistral-small",
        }


def get_ollama_models() -> dict:
    try:
        return api_get("/ollama/models")
    except requests.RequestException as exc:
        return {"available": False, "models": [], "error": str(exc), "base_url": ""}


def render_generate_page(project: dict | None) -> None:
    left, right = st.columns([2.15, 1], gap="large")
    with right:
        render_agent_card()

    with left:
        if not project:
            st.info("Create a project in the sidebar to start generating documents.")
            return

        documents = project.get("documents", [])
        templates = project.get("templates", [])
        model_settings = get_model_settings()

        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="metric-card"><b>{len(documents)}</b><br><span class="small-muted">Source documents</span></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><b>{sum(doc.get("chunks", 0) for doc in documents)}</b><br><span class="small-muted">Knowledge chunks</span></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><b>{len(templates)}</b><br><span class="small-muted">DOCX templates</span></div>', unsafe_allow_html=True)

        st.write("")
        with st.container(border=True):
            st.subheader("Generation workflow")
            title = st.text_input("Document title", value="Generated Document")
            prompt = st.text_area("Document brief", height=150, placeholder="Describe the document you want to produce.")
            section_text = st.text_area("Required sections, one per line", height=110)
            template_choices = {"No template": None}
            template_choices.update({item["filename"]: item["id"] for item in templates})
            template_label = st.selectbox("Template", list(template_choices.keys()))

            generate = st.button("Generate DOCX", type="primary", disabled=not prompt.strip())

        if generate:
            required_sections = [line.strip() for line in section_text.splitlines() if line.strip()] or None
            progress = st.progress(0, text="Preparing workflow")
            set_workflow(active="Clarification")
            time.sleep(0.15)
            progress.progress(12, text="Clarification complete")
            set_workflow(active="Planner", done=["Clarification"])
            time.sleep(0.15)
            progress.progress(26, text="Planning section graph")
            set_workflow(active="Retriever", done=["Clarification", "Planner"])
            time.sleep(0.15)
            progress.progress(42, text="Retrieving scoped context")
            set_workflow(active="Writer", done=["Clarification", "Planner", "Retriever"])

            with st.spinner("Generating with Ollama agents"):
                result = api_post(
                    "/generate",
                    json={
                        "project_id": project["id"],
                        "title": title,
                        "prompt": prompt,
                        "required_sections": required_sections,
                        "template_id": template_choices[template_label],
                        "model_overrides": model_settings,
                    },
                )

            progress.progress(72, text="Validating generated sections")
            set_workflow(active="Validator", done=["Clarification", "Planner", "Retriever", "Writer"])
            time.sleep(0.15)
            progress.progress(86, text="Editing final prose")
            set_workflow(active="Editor", done=["Clarification", "Planner", "Retriever", "Writer", "Validator"])
            time.sleep(0.15)
            progress.progress(100, text="DOCX export ready")
            set_workflow(done=list(st.session_state.workflow_steps.keys()))
            st.session_state.last_result = result
            st.success("Document generated.")

        if st.session_state.last_result:
            result = st.session_state.last_result
            st.markdown("### Latest result")
            st.link_button("Download DOCX", f"{st.session_state.api_url}/download/{project['id']}/{result['run_id']}")
            for section in result["sections"]:
                verdict = section.get("validation", {}).get("verdict", "review")
                with st.expander(f"{section['title']} · {verdict}"):
                    st.write(section["content"])
                    st.json(section.get("validation", {}))


def render_documents_settings(project: dict | None) -> None:
    if not project:
        st.info("Create a project first.")
        return

    model_settings = get_model_settings()
    st.subheader("Upload and manage knowledge")
    uploaded = st.file_uploader("Source documents", type=["pdf", "docx", "txt", "md"], accept_multiple_files=True)
    if st.button("Ingest selected documents", disabled=not uploaded):
        for file in uploaded or []:
            with st.spinner(f"Ingesting {file.name}"):
                result = api_post(
                    "/upload",
                    files={"file": (file.name, file.getvalue())},
                    data={"project_id": project["id"], "embedding_model": model_settings["embedding_model"]},
                )
                st.write(result)
        st.rerun()

    documents = project.get("documents", [])
    st.markdown("#### Document library")
    if documents:
        st.dataframe(
            [
                {
                    "Filename": item["filename"],
                    "Chunks": item["chunks"],
                    "Hash": item["sha256"][:16],
                    "Document ID": item["id"],
                }
                for item in documents
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No documents ingested yet.")

    st.markdown("#### Retrieval test")
    query = st.text_input("Search knowledge base")
    if st.button("Search", disabled=not query.strip()):
        results = api_post("/retrieval/search", json={"project_id": project["id"], "query": query, "top_k": 8})
        for item in results:
            with st.expander(f"{item['metadata'].get('filename', item['document_id'])} · {item['score']:.3f}"):
                st.write(item["text"])
                st.json(item["metadata"])


def render_template_settings(project: dict | None) -> None:
    if not project:
        st.info("Create a project first.")
        return
    st.subheader("Template manager")
    template_file = st.file_uploader("DOCX template", type=["docx"])
    if st.button("Save template", disabled=not template_file):
        result = api_post(
            "/template",
            files={"file": (template_file.name, template_file.getvalue())},
            data={"project_id": project["id"]},
        )
        st.success(f"Saved {result['filename']}")
        st.rerun()

    templates = project.get("templates", [])
    if templates:
        st.dataframe(
            [
                {
                    "Filename": item["filename"],
                    "Placeholders": len(item["profile"].get("placeholders", [])),
                    "Styles read": len(item["profile"].get("styles", [])),
                    "Template ID": item["id"],
                }
                for item in templates
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No templates uploaded yet.")


def render_ollama_settings() -> None:
    st.subheader("Ollama model management")
    model_settings = get_model_settings()
    ollama = get_ollama_models()

    if ollama["available"]:
        st.success(f"Ollama connected at {ollama['base_url']}")
    else:
        st.warning(f"Ollama is not reachable at {ollama.get('base_url') or st.session_state.api_url}")
        if ollama.get("error"):
            st.caption(ollama["error"])

    discovered = ollama.get("models", [])
    default_options = [
        "qwen3:14b",
        "gemma3:12b",
        "mistral-small",
        "nomic-embed-text",
    ]
    options = sorted(set(discovered + default_options))

    with st.form("model_settings"):
        embedding_model = st.selectbox(
            "Embedding model",
            options,
            index=options.index(model_settings["embedding_model"]) if model_settings["embedding_model"] in options else 0,
        )
        planning_model = st.selectbox(
            "Planning model",
            options,
            index=options.index(model_settings["planning_model"]) if model_settings["planning_model"] in options else 0,
        )
        writing_model = st.selectbox(
            "Writing model",
            options,
            index=options.index(model_settings["writing_model"]) if model_settings["writing_model"] in options else 0,
        )
        validation_model = st.selectbox(
            "Validation model",
            options,
            index=options.index(model_settings["validation_model"]) if model_settings["validation_model"] in options else 0,
        )
        editing_model = st.selectbox(
            "Editing model",
            options,
            index=options.index(model_settings["editing_model"]) if model_settings["editing_model"] in options else 0,
        )

        if st.form_submit_button("Save model settings", type="primary"):
            saved = api_post(
                "/settings/models",
                json={
                    "embedding_model": embedding_model,
                    "planning_model": planning_model,
                    "writing_model": writing_model,
                    "validation_model": validation_model,
                    "editing_model": editing_model,
                },
            )
            st.success("Model settings saved.")
            st.json(saved)

    st.markdown("#### Installed Ollama models")
    if discovered:
        st.dataframe([{"Model": model} for model in discovered], use_container_width=True, hide_index=True)
    else:
        st.caption("No models reported. Pull models during setup, then operate offline.")

    with st.form("pull_model"):
        model_to_pull = st.text_input("Pull model during setup", placeholder="qwen3:14b")
        if st.form_submit_button("Pull model") and model_to_pull.strip():
            with st.spinner(f"Pulling {model_to_pull.strip()} through local Ollama"):
                result = api_post("/ollama/pull", json={"model": model_to_pull.strip()})
            st.success(f"Pulled {result['model']}")
            st.rerun()


def render_settings_page(project: dict | None) -> None:
    st.subheader("Settings")
    tab_docs, tab_templates, tab_models, tab_project = st.tabs(
        ["Document upload and management", "Template manager", "Ollama models", "Project"]
    )
    with tab_docs:
        render_documents_settings(project)
    with tab_templates:
        render_template_settings(project)
    with tab_models:
        render_ollama_settings()
    with tab_project:
        if project:
            st.json(project)
            st.markdown("#### Project events")
            try:
                events = api_get(f"/projects/{project['id']}/events")
                if events:
                    st.dataframe(events[-50:], use_container_width=True, hide_index=True)
                else:
                    st.caption("No events recorded yet.")
            except requests.RequestException:
                st.caption("Events are not available.")
        else:
            st.info("No active project.")


st.session_state.dark_mode = st.sidebar.toggle("Dark mode", value=st.session_state.dark_mode)
inject_css(st.session_state.dark_mode)
render_header()

try:
    health = api_get("/health")
    st.sidebar.success(f"Backend: {health['status']} · {health['llm']}")
except requests.RequestException:
    st.sidebar.error("Backend is not reachable")

projects = load_projects()
render_project_picker(projects)
project = selected_project(projects)

page = st.sidebar.radio("Page", ["Generate", "Settings"], label_visibility="collapsed")

if page == "Generate":
    render_generate_page(project)
else:
    render_settings_page(project)
