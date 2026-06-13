"""
Document generation workflow with parallel section execution and Agentic RAG loops.

Pipeline flow:
  1. Planner Agent   – generates a section plan.
  2. Section 1 (root) runs serially to establish context.
  3. All remaining sections run concurrently (up to max_concurrent_sections).
  4. Each section uses an Agentic RAG loop:
       Retriever → Writer → Editor → Validator  (up to 3 iterations)
  5. Document Builder Agent – inspects template via VLM, writes + executes a
     python-docx script to compile the final styled DOCX.
  6. Redis task-tracker progress and WebSocket streaming events are emitted at each step.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.agents.document_builder.agent import DocumentBuilderAgent
from backend.agents.editor.agent import EditorAgent
from backend.agents.planner.agent import PlannerAgent
from backend.agents.retriever.agent import RetrieverAgent
from backend.agents.validator.agent import ValidatorAgent
from backend.agents.writer.agent import WriterAgent
from backend.api.task_tracker import TaskTracker
from backend.storage.filesystem.event_log import append_event
from backend.storage.filesystem.json_store import write_json
from backend.storage.filesystem.project_layout import ensure_project_layout

logger = logging.getLogger(__name__)

_AGENTIC_MAX_ITERATIONS = 3
_PROGRESS_WEIGHT_PLAN = 8   # % reserved for planning phase
_PROGRESS_WEIGHT_BUILD = 6  # % reserved for DOCX build phase


class DocumentGenerationWorkflow:
    def __init__(
        self,
        planner: PlannerAgent,
        retriever: RetrieverAgent,
        writer: WriterAgent,
        validator: ValidatorAgent,
        editor: EditorAgent,
        document_builder: DocumentBuilderAgent,
        max_concurrent: int = 6,
    ):
        self.planner = planner
        self.retriever = retriever
        self.writer = writer
        self.validator = validator
        self.editor = editor
        self.document_builder = document_builder
        self.max_concurrent = max_concurrent

    # ─────────────────────────── Public entry point ──────────────────────────

    def run(
        self,
        project_dir: Path,
        title: str,
        prompt: str,
        required_sections: list[str] | None = None,
        template_path: Path | None = None,
        task_id: str | None = None,
    ) -> dict:
        """Synchronous wrapper – runs the async pipeline in a dedicated event loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("closed")
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(
                self._run_async(project_dir, title, prompt, required_sections, template_path, task_id)
            )
        finally:
            pass  # keep loop alive for process lifetime

    # ─────────────────────────── Async pipeline ──────────────────────────────

    async def _run_async(
        self,
        project_dir: Path,
        title: str,
        prompt: str,
        required_sections: list[str] | None,
        template_path: Path | None,
        task_id: str | None,
    ) -> dict:
        run_id = str(uuid4())
        layout = ensure_project_layout(project_dir)
        event_log = layout["logs"] / "events.json"

        append_event(event_log, "generation.started", f"Started generation '{title}'", {"run_id": run_id})
        await self._emit(task_id, "generation.started", 0, "🧠 Planner Agent: building section plan…")
        await self._update_task(task_id, 0, "Planner Agent: building section plan…")

        # ── 1. Plan ──────────────────────────────────────────────────────────
        sections_plan: list[dict] = await asyncio.get_event_loop().run_in_executor(
            None, self.planner.plan, prompt, required_sections
        )
        total = len(sections_plan)
        logger.info("Plan ready: %d sections", total)
        await self._emit(task_id, "generation.section.planning", _PROGRESS_WEIGHT_PLAN,
                         f"🧠 Planner Agent: plan ready – {total} sections")
        await self._update_task(task_id, _PROGRESS_WEIGHT_PLAN, f"Planner Agent: plan ready – {total} sections")

        # ── 2. Generate sections ─────────────────────────────────────────────
        generated_sections: list[dict] = []
        section_progress_pool = 100 - _PROGRESS_WEIGHT_PLAN - _PROGRESS_WEIGHT_BUILD  # ~86%

        if not sections_plan:
            logger.warning("Empty section plan – returning minimal document.")
        elif total == 1:
            sec = await self._generate_section_agentic(
                sections_plan[0], prompt, project_dir, run_id,
                adjacent_summary="", idx=0, total=1, task_id=task_id,
                progress_pool=section_progress_pool,
            )
            generated_sections.append(sec)
        else:
            # Root section runs first to provide context for all others
            root = sections_plan[0]
            root_sec = await self._generate_section_agentic(
                root, prompt, project_dir, run_id,
                adjacent_summary="", idx=0, total=total, task_id=task_id,
                progress_pool=section_progress_pool,
            )
            generated_sections.append(root_sec)
            adjacent_root = f"{root['title']}: {root_sec['content'][:400]}"

            # All remaining sections run in parallel batches
            remaining = sections_plan[1:]
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def bounded(section: dict, idx: int) -> dict:
                async with semaphore:
                    return await self._generate_section_agentic(
                        section, prompt, project_dir, run_id,
                        adjacent_summary=adjacent_root,
                        idx=idx + 1, total=total, task_id=task_id,
                        progress_pool=section_progress_pool,
                    )

            tasks = [bounded(s, i) for i, s in enumerate(remaining)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.error("Section generation failed: %s", res)
                    generated_sections.append({
                        **remaining[i],
                        "content": f"[Section generation failed: {res}]",
                        "validation": {"valid": False, "summary": str(res)},
                        "sources": [],
                    })
                else:
                    generated_sections.append(res)

        # Re-order to match the original plan order
        plan_ids = [s["id"] for s in sections_plan]
        generated_sections.sort(
            key=lambda s: plan_ids.index(s["id"]) if s["id"] in plan_ids else 999
        )

        # ── 3. Document Builder (VLM + python-docx) ──────────────────────────
        build_start_pct = _PROGRESS_WEIGHT_PLAN + section_progress_pool  # ~94%
        await self._emit(task_id, "generation.editing", build_start_pct,
                         "📄 Document Builder Agent: generating styled DOCX script…")
        await self._update_task(task_id, build_start_pct,
                                "Document Builder Agent: generating styled DOCX script…")

        docx_path = layout["generated"] / f"{run_id}.docx"
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                self.document_builder.build,
                title, generated_sections, docx_path, template_path,
            )
        except Exception as exc:
            logger.error("DocumentBuilderAgent failed: %s", exc)
            # Last-resort plain compile
            from backend.exporters.docx.compiler import compile_docx
            compile_docx(title, generated_sections, docx_path, template_path=template_path)

        result = {
            "run_id": run_id,
            "title": title,
            "sections": generated_sections,
            "docx_path": str(docx_path),
        }
        write_json(project_dir / "runs" / run_id / "run.json", result)
        append_event(event_log, "generation.completed", f"Completed '{title}'",
                     {"run_id": run_id, "docx_path": str(docx_path)})

        await self._emit(task_id, "generation.completed", 100, "✅ Document ready")
        await self._update_task(task_id, 100, "Done")
        return result

    # ─────────────────────────── Agentic RAG loop ────────────────────────────

    async def _generate_section_agentic(
        self,
        section: dict,
        prompt: str,
        project_dir: Path,
        run_id: str,
        adjacent_summary: str,
        idx: int,
        total: int,
        task_id: str | None,
        progress_pool: int,
    ) -> dict:
        """Retriever → Writer → Editor → Validator loop (up to _AGENTIC_MAX_ITERATIONS)."""
        title = section["title"]
        # Base section progress (progress advances uniformly across sections)
        section_pct = _PROGRESS_WEIGHT_PLAN + int((idx / max(total, 1)) * progress_pool)

        loop = asyncio.get_event_loop()

        # ── Retriever ──────────────────────────────────────────────────────
        await self._emit(task_id, "generation.section.writing", section_pct,
                         f"🔍 Retriever Agent: fetching context for '{title}' ({idx+1}/{total})")
        await self._update_task(task_id, section_pct,
                                f"Retriever Agent: fetching context for '{title}' ({idx+1}/{total})")
        logger.info("Generating section [%d/%d]: %s", idx + 1, total, title)

        query = f"{prompt}\n{title}\n{' '.join(section.get('required_context', []))}"
        retrieved = await loop.run_in_executor(None, self.retriever.retrieve, query, 6)

        retrieval_record = {
            "section_id": section["id"],
            "query": query,
            "results": [
                {"chunk_id": r.chunk_id, "document_id": r.document_id, "score": r.score, "metadata": r.metadata}
                for r in retrieved
            ],
        }
        write_json(project_dir / "runs" / run_id / f"retrieval_{section['id']}.json", retrieval_record)

        # ── Writer → Editor → Validator loop ─────────────────────────────
        critic_feedback: str = ""
        content: str = ""
        validation: dict = {}

        for iteration in range(1, _AGENTIC_MAX_ITERATIONS + 1):
            # ── Writer ──────────────────────────────────────────────────
            augmented_adjacent = adjacent_summary
            if critic_feedback:
                augmented_adjacent = (
                    f"{adjacent_summary}\n\n[Critic feedback (iter {iteration-1})]: {critic_feedback}"
                )

            await self._emit(task_id, "generation.section.writing", section_pct,
                             f"✍️ Writer Agent: drafting '{title}' (iter {iteration}/{_AGENTIC_MAX_ITERATIONS})")
            await self._update_task(task_id, section_pct,
                                    f"Writer Agent: drafting '{title}' (iter {iteration}/{_AGENTIC_MAX_ITERATIONS})")

            content = await loop.run_in_executor(
                None,
                self.writer.write_section,
                title, prompt, retrieved, augmented_adjacent,
            )

            # ── Editor ──────────────────────────────────────────────────
            await self._emit(task_id, "generation.section.writing", section_pct,
                             f"✏️ Editor Agent: polishing '{title}' (iter {iteration}/{_AGENTIC_MAX_ITERATIONS})")
            await self._update_task(task_id, section_pct,
                                    f"Editor Agent: polishing '{title}' (iter {iteration}/{_AGENTIC_MAX_ITERATIONS})")

            content = await loop.run_in_executor(None, self.editor.edit, title, content)

            # ── Validator ────────────────────────────────────────────────
            await self._emit(task_id, "generation.section.validating", section_pct,
                             f"🔎 Validator Agent: checking '{title}' (iter {iteration}/{_AGENTIC_MAX_ITERATIONS})")
            await self._update_task(task_id, section_pct,
                                    f"Validator Agent: checking '{title}' (iter {iteration}/{_AGENTIC_MAX_ITERATIONS})")

            validation = await loop.run_in_executor(None, self.validator.validate, title, content)

            if validation.get("valid", True):
                logger.info("Section '%s' passed validation on iteration %d", title, iteration)
                break

            critic_feedback = validation.get("summary", "")
            logger.info("Section '%s' failed validation (iter %d): %s", title, iteration, critic_feedback)

        sources = [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "score": r.score,
                "filename": r.metadata.get("filename"),
            }
            for r in retrieved
        ]

        sec_result = {**section, "content": content, "validation": validation, "sources": sources}

        write_json(
            project_dir / "runs" / run_id / "section_outputs.json",
            {"section_id": section["id"], "result": sec_result},
        )
        append_event(
            project_dir / "logs" / "events.json",
            "generation.section_completed",
            f"Completed section '{title}'",
            {"run_id": run_id, "section_id": section["id"], "validation": validation},
        )
        await self._emit(task_id, "generation.section.completed", section_pct, f"✅ Done: '{title}'")
        return sec_result

    # ─────────────────────────── Helpers ─────────────────────────────────────

    @staticmethod
    async def _emit(
        task_id: str | None,
        event_type: str,
        progress: int,
        message: str,
    ) -> None:
        """Fire a streaming WebSocket event (best-effort – never throws)."""
        if not task_id:
            return
        try:
            from backend.streaming import get_stream_manager, GenerationEvent, GenerationEventType
            from datetime import datetime

            evt_map = {
                "generation.started": GenerationEventType.STARTED,
                "generation.section.planning": GenerationEventType.SECTION_PLANNING,
                "generation.section.writing": GenerationEventType.SECTION_WRITING,
                "generation.section.validating": GenerationEventType.SECTION_VALIDATING,
                "generation.section.completed": GenerationEventType.SECTION_COMPLETED,
                "generation.editing": GenerationEventType.EDITING,
                "generation.completed": GenerationEventType.COMPLETED,
            }

            evt = GenerationEvent(
                event_type=evt_map.get(event_type, GenerationEventType.STARTED),
                task_id=task_id,
                progress=progress,
                message=message,
                section_title=None,
                timestamp=datetime.utcnow(),
            )
            manager = get_stream_manager()
            await manager.emit(task_id, evt)
        except Exception:
            pass  # streaming is best-effort

    @staticmethod
    async def _update_task(task_id: str | None, progress: int, message: str) -> None:
        """Best-effort update of Redis / in-memory task tracker."""
        if not task_id:
            return
        try:
            tracker = TaskTracker()
            tracker.update_progress(task_id, progress, message)
        except Exception:
            pass
