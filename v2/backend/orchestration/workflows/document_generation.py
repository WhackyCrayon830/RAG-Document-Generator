from pathlib import Path
from uuid import uuid4

from backend.agents.editor.agent import EditorAgent
from backend.agents.planner.agent import PlannerAgent
from backend.agents.retriever.agent import RetrieverAgent
from backend.agents.validator.agent import ValidatorAgent
from backend.agents.writer.agent import WriterAgent
from backend.exporters.docx.compiler import compile_docx
from backend.storage.filesystem.event_log import append_event
from backend.storage.filesystem.json_store import write_json
from backend.storage.filesystem.project_layout import ensure_project_layout


class DocumentGenerationWorkflow:
    def __init__(
        self,
        planner: PlannerAgent,
        retriever: RetrieverAgent,
        writer: WriterAgent,
        validator: ValidatorAgent,
        editor: EditorAgent,
    ):
        self.planner = planner
        self.retriever = retriever
        self.writer = writer
        self.validator = validator
        self.editor = editor

    def run(
        self,
        project_dir: Path,
        title: str,
        prompt: str,
        required_sections: list[str] | None = None,
        template_path: Path | None = None,
    ) -> dict:
        run_id = str(uuid4())
        layout = ensure_project_layout(project_dir)
        append_event(layout["logs"] / "events.json", "generation.started", f"Started generation {title}", {"run_id": run_id})
        sections_plan = self.planner.plan(prompt, required_sections)
        generated_sections = []
        adjacent_summary = ""

        for section in sections_plan:
            query = f"{prompt}\n{section['title']}\n{' '.join(section.get('required_context', []))}"
            retrieved = self.retriever.retrieve(query, top_k=6)
            write_json(
                project_dir / "runs" / run_id / f"retrieval_{section['id']}.json",
                {
                    "section_id": section["id"],
                    "query": query,
                    "results": [
                        {
                            "chunk_id": item.chunk_id,
                            "document_id": item.document_id,
                            "score": item.score,
                            "metadata": item.metadata,
                        }
                        for item in retrieved
                    ],
                },
            )
            draft = self.writer.write_section(section["title"], prompt, retrieved, adjacent_summary)
            edited = self.editor.edit(section["title"], draft)
            validation = self.validator.validate(section["title"], edited)
            generated_sections.append(
                {
                    **section,
                    "content": edited,
                    "validation": validation,
                    "sources": [
                        {
                            "chunk_id": item.chunk_id,
                            "document_id": item.document_id,
                            "score": item.score,
                            "filename": item.metadata.get("filename"),
                        }
                        for item in retrieved
                    ],
                }
            )
            adjacent_summary = f"{section['title']}: {edited[:500]}"
            write_json(project_dir / "runs" / run_id / "section_outputs.json", generated_sections)
            append_event(
                layout["logs"] / "events.json",
                "generation.section_completed",
                f"Completed section {section['title']}",
                {"run_id": run_id, "section_id": section["id"], "validation": validation},
            )

        docx_path = layout["generated"] / f"{run_id}.docx"
        compile_docx(title, generated_sections, docx_path, template_path=template_path)
        result = {"run_id": run_id, "title": title, "sections": generated_sections, "docx_path": str(docx_path)}
        write_json(project_dir / "runs" / run_id / "run.json", result)
        append_event(layout["logs"] / "events.json", "generation.completed", f"Completed generation {title}", {"run_id": run_id, "docx_path": str(docx_path)})
        return result
