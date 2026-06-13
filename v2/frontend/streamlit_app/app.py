"""
RAG Document Generator – Streamlit Dashboard
- Two top-level tabs: Generate | Settings
- @st.cache_data for all backend reads (invalidated on writes)
- Async task polling for progress updates without page reloads
- HTML rendered properly via unsafe_allow_html=True (no indented code block trap)
- Settings tab exposes all configurable backend settings
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
import streamlit as st

DEFAULT_API_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="RAG Document Generator",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"About": "Offline RAG Document Generator v2"},
)


# ─────────────────────────────── Session state ───────────────────────────────

def init_state() -> None:
    defaults: dict = {
        "api_url": DEFAULT_API_URL,
        "dark_mode": True,
        "active_project_id": None,
        "last_result": None,
        "last_task_id": None,
        "workflow_steps": {
            "🧠 Planner Agent": "Waiting",
            "🔍 Retriever Agent": "Waiting",
            "✍️ Writer Agent": "Waiting",
            "✏️ Editor Agent": "Waiting",
            "🔎 Validator Agent": "Waiting",
            "📄 Document Builder": "Waiting",
        },
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


init_state()


# ─────────────────────────────── CSS / Theming ───────────────────────────────

def inject_css(dark_mode: bool) -> None:
    if dark_mode:
        c = {
            "bg": "#0f1117",
            "panel": "#171b24",
            "panel2": "#202634",
            "text": "#f2f4f8",
            "muted": "#9aa4b2",
            "border": "#2d3545",
            "accent": "#5dd6c7",
            "ok": "#64d887",
            "warn": "#f2c66d",
            "err": "#ff6b6b",
        }
    else:
        c = {
            "bg": "#f6f7fb",
            "panel": "#ffffff",
            "panel2": "#eef2f7",
            "text": "#161a22",
            "muted": "#627084",
            "border": "#d9e0ea",
            "accent": "#176b87",
            "ok": "#207a45",
            "warn": "#9b6417",
            "err": "#c0392b",
        }

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
.stApp {{ background: {c["bg"]}; color: {c["text"]}; }}
[data-testid="stHeader"] {{ background: transparent; }}
.main .block-container {{ max-width: 1380px; padding-top: 1.5rem; }}
.app-title {{ font-size: 2rem; font-weight: 760; letter-spacing: -0.5px; margin-bottom: .15rem; }}
.app-subtitle {{ color: {c["muted"]}; font-size: .95rem; margin-bottom: 1rem; }}
.metric-card, .agent-card, .soft-card {{
    background: {c["panel"]};
    border: 1px solid {c["border"]};
    border-radius: 14px;
    padding: 1rem 1.2rem;
    box-shadow: 0 4px 20px rgba(0,0,0,.06);
}}
.agent-card {{ position: sticky; top: 1rem; }}
.card-title {{ font-size: 1rem; font-weight: 700; margin-bottom: .75rem; color: {c["text"]}; }}
.step-row {{
    display: flex; align-items: center; justify-content: space-between;
    gap: .6rem; border-bottom: 1px solid {c["border"]}; padding: .55rem 0;
}}
.step-row:last-child {{ border-bottom: 0; }}
.step-name {{ color: {c["text"]}; font-weight: 600; font-size: .9rem; }}
.pill {{
    border-radius: 999px; padding: .18rem .52rem;
    font-size: .75rem; white-space: nowrap;
    background: {c["panel2"]}; color: {c["muted"]};
    border: 1px solid {c["border"]};
}}
.pill-done {{ color: {c["ok"]}; border-color: {c["ok"]}; background: transparent; }}
.pill-active {{ color: {c["accent"]}; border-color: {c["accent"]}; background: transparent; }}
.pill-review {{ color: {c["warn"]}; border-color: {c["warn"]}; background: transparent; }}
.pill-error {{ color: {c["err"]}; border-color: {c["err"]}; background: transparent; }}
.small-muted {{ color: {c["muted"]}; font-size: .88rem; }}
div[data-testid="stTabs"] button {{ border-radius: 999px; font-weight: 600; }}
div.stButton > button, div[data-testid="stDownloadButton"] button {{
    border-radius: 10px; font-weight: 650;
}}
.settings-section-header {{
    font-size: 1rem; font-weight: 700; color: {c["accent"]};
    margin-top: 1.2rem; margin-bottom: .4rem;
    border-bottom: 1px solid {c["border"]}; padding-bottom: .3rem;
}}
</style>""", unsafe_allow_html=True)


# ─────────────────────────────── API helpers ─────────────────────────────────

def _url(path: str) -> str:
    return f"{st.session_state.api_url}{path}"


def api_get(path: str, timeout: int = 20):
    r = requests.get(_url(path), timeout=timeout)
    r.raise_for_status()
    return r.json()


def api_post(path: str, json=None, files=None, data=None, timeout: int = 600):
    r = requests.post(_url(path), json=json, files=files, data=data, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ── Cached data fetches ───────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def load_projects(_api: str) -> list[dict]:
    try:
        return api_get("/projects")
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_project(_api: str, project_id: str) -> dict | None:
    try:
        return api_get(f"/projects/{project_id}")
    except Exception:
        return None


@st.cache_data(ttl=120, show_spinner=False)
def fetch_model_settings(_api: str) -> dict:
    try:
        return api_get("/settings/models")
    except Exception:
        return {
            "embedding_model": "nomic-embed-text",
            "planning_model": "qwen3:14b",
            "writing_model": "qwen3:14b",
            "validation_model": "gemma3:12b",
            "editing_model": "mistral-small",
        }


@st.cache_data(ttl=120, show_spinner=False)
def fetch_general_settings(_api: str) -> dict:
    try:
        return api_get("/settings/general")
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def fetch_ollama_models(_api: str) -> dict:
    try:
        return api_get("/ollama/models")
    except Exception as exc:
        return {"available": False, "models": [], "error": str(exc), "base_url": ""}


# ─────────────────────────────── Shared UI ───────────────────────────────────

def render_header() -> None:
    left, right = st.columns([3, 1])
    with left:
        st.markdown('<div class="app-title">Offline RAG Document Generator</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="app-subtitle">Generate template-aware documents with local Ollama agents and hybrid retrieval.</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.session_state.api_url = st.text_input(
            "Backend URL", value=st.session_state.api_url, label_visibility="collapsed"
        )


def status_pill(status: str) -> str:
    css_map = {"Complete": "pill-done", "Running": "pill-active",
               "Review": "pill-review", "Failed": "pill-error"}
    extra = css_map.get(status, "")
    return f'<span class="pill {extra}">{status}</span>'


def render_agent_card() -> None:
    rows = "".join(
        f'<div class="step-row"><span class="step-name">{name}</span>{status_pill(status)}</div>'
        for name, status in st.session_state.workflow_steps.items()
    )
    html = (
        '<div class="agent-card">'
        '<div class="card-title">Agentic RAG Pipeline</div>'
        + rows
        + '<div class="small-muted" style="margin-top:.65rem;">'
        "Each section runs through an autonomous Retrieve → Write → Edit → Validate loop "
        "with up to 3 self-correction iterations. Sections generate in parallel. "
        "The Document Builder Agent uses a VLM to analyse the template and writes a python-docx script to compile the final styled DOCX."
        "</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)


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


# ─────────────────────────────── Project sidebar ─────────────────────────────

def render_project_picker(projects: list[dict]) -> None:
    api = st.session_state.api_url
    with st.sidebar:
        st.markdown("### Workspace")
        if projects:
            labels = {f"{p['name']} · {p['id'][:8]}": p["id"] for p in projects}
            current = next(
                (lbl for lbl, pid in labels.items() if pid == st.session_state.active_project_id),
                list(labels.keys())[0],
            )
            choice = st.selectbox("Project", list(labels.keys()),
                                  index=list(labels.keys()).index(current),
                                  key="proj_picker")
            new_pid = labels[choice]
            if new_pid != st.session_state.active_project_id:
                st.session_state.active_project_id = new_pid
                # Do NOT call st.rerun() – just let next render pick it up
        with st.form("create_project", clear_on_submit=True):
            name = st.text_input("New project name", key="new_proj_name")
            if st.form_submit_button("Create project") and name.strip():
                project = api_post("/projects", json={"name": name.strip()})
                st.session_state.active_project_id = project["id"]
                load_projects.clear()
                st.rerun()
        st.sidebar.toggle("Dark mode", value=st.session_state.dark_mode, key="dark_mode")


# ─────────────────────────────── Generate tab ────────────────────────────────

def render_generate_tab(project: dict | None) -> None:
    left, right = st.columns([2.2, 1], gap="large")
    with right:
        render_agent_card()

    with left:
        if not project:
            st.info("Create or select a project in the sidebar to start generating documents.")
            return

        documents = project.get("documents", [])
        templates = project.get("templates", [])
        model_settings = fetch_model_settings(st.session_state.api_url)

        c1, c2, c3 = st.columns(3)
        c1.markdown(
            f'<div class="metric-card"><b>{len(documents)}</b><br><span class="small-muted">Source documents</span></div>',
            unsafe_allow_html=True,
        )
        c2.markdown(
            f'<div class="metric-card"><b>{sum(d.get("chunks", 0) for d in documents)}</b><br><span class="small-muted">Knowledge chunks</span></div>',
            unsafe_allow_html=True,
        )
        c3.markdown(
            f'<div class="metric-card"><b>{len(templates)}</b><br><span class="small-muted">DOCX templates</span></div>',
            unsafe_allow_html=True,
        )

        st.write("")
        with st.container(border=True):
            st.subheader("Generation workflow")
            title = st.text_input("Document title", value="Generated Document", key="gen_title")
            prompt = st.text_area("Document brief", height=130,
                                  placeholder="Describe the document you want to produce.",
                                  key="gen_prompt")
            section_text = st.text_area("Required sections (one per line)", height=100,
                                        key="gen_sections")
            template_choices: dict[str, str | None] = {"No template": None}
            template_choices.update({item["filename"]: item["id"] for item in templates})
            template_label = st.selectbox("Template", list(template_choices.keys()), key="gen_template")

            col_btn, col_async = st.columns([1, 1])
            generate_sync = col_btn.button("Generate (sync)", type="primary", disabled=not prompt.strip(),
                                           key="gen_sync")
            generate_async = col_async.button("Generate (async + live progress)",
                                              disabled=not prompt.strip(), key="gen_async")

        # ── Sync generation ──────────────────────────────────────────────────
        if generate_sync:
            required_sections = [l.strip() for l in section_text.splitlines() if l.strip()] or None
            progress = st.progress(0, text="Preparing workflow")
            set_workflow(active="🧠 Planner Agent")
            time.sleep(0.1)
            with st.spinner("Running Agentic RAG pipeline in backend…"):
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
            progress.progress(100, text="Generation complete")
            set_workflow(done=list(st.session_state.workflow_steps.keys()))
            st.session_state.last_result = result
            st.session_state.last_task_id = None
            st.success("Document generated.")

        # ── Async generation with live progress polling ───────────────────────
        if generate_async:
            required_sections = [l.strip() for l in section_text.splitlines() if l.strip()] or None
            resp = api_post(
                "/generate/async",
                json={
                    "project_id": project["id"],
                    "title": title,
                    "prompt": prompt,
                    "required_sections": required_sections,
                    "template_id": template_choices[template_label],
                    "model_overrides": model_settings,
                },
            )
            task_id = resp["task_id"]
            st.session_state.last_task_id = task_id
            st.session_state.last_result = None
            st.info(f"Task queued: `{task_id}` — polling for progress…")
            _poll_task_progress(task_id, project)

        # ── Resume polling if a task is in flight ─────────────────────────────
        elif st.session_state.last_task_id and not st.session_state.last_result:
            if st.button("🔄 Resume polling", key="resume_poll"):
                _poll_task_progress(st.session_state.last_task_id, project)

        # ── Show last result ──────────────────────────────────────────────────
        _render_last_result(project)


def _poll_task_progress(task_id: str, project: dict) -> None:
    """Poll /tasks/{task_id}/status and update UI until done."""
    progress_bar = st.progress(0, text="Queued…")
    status_text = st.empty()
    max_polls = 720  # ~12 min at 1-second intervals

    # Message-keyword → (active step, completed steps)
    _AGENT_KEYWORDS = [
        ("Planner Agent",          "🧠 Planner Agent",     []),
        ("Retriever Agent",        "🔍 Retriever Agent",   ["🧠 Planner Agent"]),
        ("Writer Agent",           "✍️ Writer Agent",       ["🧠 Planner Agent", "🔍 Retriever Agent"]),
        ("Editor Agent",           "✏️ Editor Agent",       ["🧠 Planner Agent", "🔍 Retriever Agent", "✍️ Writer Agent"]),
        ("Validator Agent",        "🔎 Validator Agent",   ["🧠 Planner Agent", "🔍 Retriever Agent", "✍️ Writer Agent", "✏️ Editor Agent"]),
        ("Document Builder Agent", "📄 Document Builder",  ["🧠 Planner Agent", "🔍 Retriever Agent", "✍️ Writer Agent", "✏️ Editor Agent", "🔎 Validator Agent"]),
    ]

    for _ in range(max_polls):
        try:
            s = api_get(f"/tasks/{task_id}/status", timeout=10)
        except Exception:
            time.sleep(2)
            continue

        pct = s.get("progress", 0) or 0
        msg = s.get("current", "Working…") or "Working…"
        status_val = s.get("status", "started")

        progress_bar.progress(min(pct, 100), text=msg)
        status_text.caption(f"Status: **{status_val}** · {pct}%")

        # Update workflow card based on message keywords
        matched = False
        for keyword, active, done in _AGENT_KEYWORDS:
            if keyword.lower() in msg.lower():
                set_workflow(active=active, done=done)
                matched = True
                break
        # Fallback: use progress % to guess step
        if not matched:
            if pct < 8:
                set_workflow(active="🧠 Planner Agent", done=[])
            elif pct < 90:
                set_workflow(active="✍️ Writer Agent", done=["🧠 Planner Agent", "🔍 Retriever Agent"])
            elif pct < 98:
                set_workflow(active="📄 Document Builder", done=["🧠 Planner Agent", "🔍 Retriever Agent", "✍️ Writer Agent", "✏️ Editor Agent", "🔎 Validator Agent"])

        if status_val in ("success", "failure", "revoked"):
            if status_val == "success":
                set_workflow(done=list(st.session_state.workflow_steps.keys()))
                progress_bar.progress(100, text="Done!")
                if s.get("result"):
                    try:
                        st.session_state.last_result = s["result"]
                    except Exception:
                        st.session_state.last_result = s.get("result", {})
                st.session_state.last_task_id = None
                st.success("Generation complete!")
            elif status_val == "failure":
                st.error(f"Generation failed: {s.get('error', 'Unknown error')}")
                st.session_state.last_task_id = None
            else:
                st.warning("Task was cancelled.")
                st.session_state.last_task_id = None
            break

        time.sleep(1)


def _render_last_result(project: dict) -> None:
    """Display the most recent generation result and download link."""
    result = st.session_state.last_result
    if not result:
        return
    run_id = result.get("run_id") or result.get("run_id", "")
    st.markdown("### Latest result")
    if run_id:
        st.link_button(
            "⬇ Download DOCX",
            f"{st.session_state.api_url}/download/{project['id']}/{run_id}",
        )
    sections = result.get("sections", [])
    if sections:
        for section in sections:
            verdict = section.get("validation", {}).get("verdict", "review")
            with st.expander(f"{section.get('title', 'Section')} · {verdict}"):
                st.write(section.get("content", ""))
                val = section.get("validation", {})
                if val:
                    st.json(val)


# ─────────────────────────────── Settings tab ────────────────────────────────

def render_settings_tab(project: dict | None) -> None:
    tab_docs, tab_tpl, tab_models, tab_general, tab_proj = st.tabs([
        "📂 Documents",
        "📄 Templates",
        "🤖 Ollama Models",
        "⚙ General Config",
        "🗂 Project",
    ])

    with tab_docs:
        _render_documents(project)
    with tab_tpl:
        _render_templates(project)
    with tab_models:
        _render_ollama_settings()
    with tab_general:
        _render_general_settings()
    with tab_proj:
        _render_project_info(project)


def _render_documents(project: dict | None) -> None:
    if not project:
        st.info("Select or create a project first.")
        return
    api = st.session_state.api_url
    model_settings = fetch_model_settings(api)
    st.subheader("Upload and manage knowledge")
    uploaded = st.file_uploader(
        "Source documents", type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True, key="doc_uploader"
    )
    if st.button("Ingest selected documents", disabled=not uploaded, key="ingest_btn"):
        for file in uploaded or []:
            with st.spinner(f"Ingesting {file.name}…"):
                result = api_post(
                    "/upload",
                    files={"file": (file.name, file.getvalue())},
                    data={"project_id": project["id"], "embedding_model": model_settings["embedding_model"]},
                )
                st.write(result)
        # Invalidate cached project data
        fetch_project.clear()
        load_projects.clear()
        st.rerun()

    documents = project.get("documents", [])
    st.markdown("#### Document library")
    if documents:
        st.dataframe(
            [{"Filename": d["filename"], "Chunks": d["chunks"],
              "Hash": d["sha256"][:16], "ID": d["id"]} for d in documents],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("No documents ingested yet.")

    st.markdown("#### Retrieval test")
    query = st.text_input("Search knowledge base", key="retrieval_query")
    if st.button("Search", disabled=not query.strip(), key="search_btn"):
        results = api_post("/retrieval/search",
                           json={"project_id": project["id"], "query": query, "top_k": 8})
        for item in results:
            fname = item["metadata"].get("filename", item["document_id"])
            with st.expander(f"{fname} · {item['score']:.3f}"):
                st.write(item["text"])
                st.json(item["metadata"])


def _render_templates(project: dict | None) -> None:
    if not project:
        st.info("Select or create a project first.")
        return
    st.subheader("Template manager")
    tpl_file = st.file_uploader("DOCX template", type=["docx"], key="tpl_uploader")
    if st.button("Save template", disabled=not tpl_file, key="save_tpl_btn"):
        result = api_post(
            "/template",
            files={"file": (tpl_file.name, tpl_file.getvalue())},
            data={"project_id": project["id"]},
        )
        st.success(f"Saved {result['filename']}")
        fetch_project.clear()
        load_projects.clear()
        st.rerun()
    templates = project.get("templates", [])
    if templates:
        st.dataframe(
            [{"Filename": t["filename"],
              "Placeholders": len(t["profile"].get("placeholders", [])),
              "Styles": len(t["profile"].get("styles", [])),
              "ID": t["id"]} for t in templates],
            use_container_width=True, hide_index=True,
        )
    else:
        st.caption("No templates uploaded yet.")


def _render_ollama_settings() -> None:
    api = st.session_state.api_url
    st.subheader("Ollama model management")
    model_settings = fetch_model_settings(api)
    ollama = fetch_ollama_models(api)

    if ollama.get("available"):
        st.success(f"Ollama connected at {ollama['base_url']}")
    else:
        st.warning(f"Ollama unreachable · {ollama.get('error', '')}")

    discovered: list[str] = ollama.get("models", [])
    default_opts = ["qwen3:14b", "gemma3:12b", "mistral-small", "nomic-embed-text", "llama3:8b", "phi3:mini"]
    options = sorted(set(discovered + default_opts))

    def idx(val: str) -> int:
        return options.index(val) if val in options else 0

    with st.form("model_settings_form"):
        embedding_model = st.selectbox("Embedding model", options, index=idx(model_settings["embedding_model"]))
        planning_model = st.selectbox("Planning model", options, index=idx(model_settings["planning_model"]))
        writing_model = st.selectbox("Writing model", options, index=idx(model_settings["writing_model"]))
        validation_model = st.selectbox("Validation model", options, index=idx(model_settings["validation_model"]))
        editing_model = st.selectbox("Editing model", options, index=idx(model_settings["editing_model"]))
        if st.form_submit_button("💾 Save model settings", type="primary"):
            saved = api_post("/settings/models", json={
                "embedding_model": embedding_model,
                "planning_model": planning_model,
                "writing_model": writing_model,
                "validation_model": validation_model,
                "editing_model": editing_model,
            })
            fetch_model_settings.clear()
            st.success("Model settings saved.")
            st.json(saved)

    st.markdown("#### Installed Ollama models")
    if discovered:
        st.dataframe([{"Model": m} for m in discovered], use_container_width=True, hide_index=True)
    else:
        st.caption("No models found. Pull models via the form below.")

    with st.form("pull_model_form"):
        model_to_pull = st.text_input("Pull model (requires internet)", placeholder="qwen3:14b")
        if st.form_submit_button("Pull model") and model_to_pull.strip():
            with st.spinner(f"Pulling {model_to_pull.strip()}…"):
                result = api_post("/ollama/pull", json={"model": model_to_pull.strip()})
            st.success(f"Pulled {result['model']}")
            fetch_ollama_models.clear()
            st.rerun()


def _render_general_settings() -> None:
    api = st.session_state.api_url
    st.subheader("General Configuration")
    st.caption("All settings are saved to the backend and take effect immediately.")

    cfg = fetch_general_settings(api)

    with st.form("general_settings_form"):
        st.markdown('<div class="settings-section-header">Ollama</div>', unsafe_allow_html=True)
        ollama_base_url = st.text_input("Ollama Base URL", value=cfg.get("ollama_base_url", "http://localhost:11434"))

        st.markdown('<div class="settings-section-header">Generation Models</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        planning_model = col1.text_input("Planning model", value=cfg.get("ollama_planning_model", "qwen3:14b"))
        writing_model = col2.text_input("Writing model", value=cfg.get("ollama_writing_model", "qwen3:14b"))
        validation_model = col1.text_input("Validation model", value=cfg.get("ollama_validation_model", "gemma3:12b"))
        editing_model = col2.text_input("Editing model", value=cfg.get("ollama_editing_model", "mistral-small"))
        embedding_model = st.text_input("Embedding model", value=cfg.get("ollama_embedding_model", "nomic-embed-text"))

        st.markdown('<div class="settings-section-header">Performance & Limits</div>', unsafe_allow_html=True)
        col3, col4, col5 = st.columns(3)
        max_upload = col3.number_input("Max upload (MB)", min_value=1, max_value=2000,
                                       value=int(cfg.get("max_upload_mb", 200)))
        gen_timeout = col4.number_input("Generation timeout (s)", min_value=60, max_value=7200,
                                        value=int(cfg.get("generation_timeout_seconds", 1800)))
        max_sections = col5.number_input("Max concurrent sections", min_value=1, max_value=10,
                                         value=int(cfg.get("max_concurrent_sections", 3)))
        worker_conc = col3.number_input("Celery worker concurrency", min_value=1, max_value=16,
                                        value=int(cfg.get("worker_concurrency", 2)))

        st.markdown('<div class="settings-section-header">Storage & Services</div>', unsafe_allow_html=True)
        col6, col7 = st.columns(2)
        app_storage_dir = col6.text_input("Storage directory", value=cfg.get("app_storage_dir", "storage"))
        redis_url = col7.text_input("Redis URL", value=cfg.get("redis_url", "redis://localhost:6379/0"))
        qdrant_url = col6.text_input("Qdrant URL", value=cfg.get("qdrant_url", "http://localhost:6333"))
        postgres_host = col7.text_input("PostgreSQL host", value=cfg.get("postgres_host", "localhost"))
        col8, col9 = st.columns(2)
        postgres_port = col8.number_input("PostgreSQL port", min_value=1, max_value=65535,
                                          value=int(cfg.get("postgres_port", 5432)))
        postgres_db = col9.text_input("PostgreSQL database", value=cfg.get("postgres_db", "rag_platform"))
        postgres_user = st.text_input("PostgreSQL user", value=cfg.get("postgres_user", "rag"))
        use_ollama = st.checkbox("Use Ollama for inference", value=bool(cfg.get("use_ollama", True)))

        if st.form_submit_button("💾 Save configuration", type="primary"):
            payload = {
                "ollama_base_url": ollama_base_url,
                "ollama_planning_model": planning_model,
                "ollama_writing_model": writing_model,
                "ollama_validation_model": validation_model,
                "ollama_editing_model": editing_model,
                "ollama_embedding_model": embedding_model,
                "use_ollama": use_ollama,
                "max_upload_mb": max_upload,
                "generation_timeout_seconds": gen_timeout,
                "max_concurrent_sections": max_sections,
                "worker_concurrency": worker_conc,
                "app_storage_dir": app_storage_dir,
                "redis_url": redis_url,
                "qdrant_url": qdrant_url,
                "postgres_host": postgres_host,
                "postgres_port": postgres_port,
                "postgres_db": postgres_db,
                "postgres_user": postgres_user,
            }
            try:
                api_post("/settings/general", json=payload)
                fetch_general_settings.clear()
                fetch_model_settings.clear()
                st.success("Configuration saved and applied.")
            except Exception as exc:
                st.error(f"Failed to save: {exc}")


def _render_project_info(project: dict | None) -> None:
    if not project:
        st.info("No active project.")
        return
    st.subheader("Project data")
    st.json(project)
    st.markdown("#### Project events")
    try:
        events = api_get(f"/projects/{project['id']}/events")
        if events:
            st.dataframe(events[-50:], use_container_width=True, hide_index=True)
        else:
            st.caption("No events recorded yet.")
    except Exception:
        st.caption("Events not available (backend unreachable?).")


# ─────────────────────────────── Main app ────────────────────────────────────

inject_css(st.session_state.dark_mode)
render_header()

try:
    health = api_get("/health", timeout=5)
    st.sidebar.success(f"Backend: {health['status']} · {health['llm']}")
except Exception:
    st.sidebar.error("Backend not reachable")

api = st.session_state.api_url
projects = load_projects(api)
render_project_picker(projects)

# Resolve active project (use cached fetch)
project: dict | None = None
if st.session_state.active_project_id:
    project = fetch_project(api, st.session_state.active_project_id)
    if not project and projects:
        st.session_state.active_project_id = projects[0]["id"]
        project = fetch_project(api, st.session_state.active_project_id)
elif projects:
    st.session_state.active_project_id = projects[0]["id"]
    project = fetch_project(api, st.session_state.active_project_id)

# ── Top-level tab navigation (replaces sidebar radio) ────────────────────────
tab_gen, tab_settings = st.tabs(["🚀 Generate Document", "⚙ Settings"])

with tab_gen:
    render_generate_tab(project)

with tab_settings:
    render_settings_tab(project)
