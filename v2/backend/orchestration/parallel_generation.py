"""Parallel section generation with dependency tracking."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SectionStatus(str, Enum):
    """Status of a section generation."""
    PENDING = "pending"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Section:
    """A document section to be generated."""
    id: str
    title: str
    prompt: str
    dependencies: list[str] = field(default_factory=list)  # Section IDs this depends on
    status: SectionStatus = SectionStatus.PENDING
    content: Optional[str] = None
    error: Optional[str] = None


class SectionGenerationOrchestrator:
    """Orchestrate parallel generation of document sections."""

    def __init__(self, max_concurrent: int = 3):
        """
        Initialize orchestrator.

        Args:
            max_concurrent: Maximum number of sections to generate in parallel
        """
        self.max_concurrent = max_concurrent
        self.sections: dict[str, Section] = {}
        self.completed: dict[str, str] = {}  # section_id -> content
        self.generation_callback: Optional[Callable] = None

    def add_section(self, section_id: str, title: str, prompt: str, dependencies: list[str] | None = None) -> None:
        """
        Add a section to the generation plan.

        Args:
            section_id: Unique section ID
            title: Section title
            prompt: Generation prompt
            dependencies: List of section IDs this depends on
        """
        self.sections[section_id] = Section(
            id=section_id,
            title=title,
            prompt=prompt,
            dependencies=dependencies or [],
        )

    async def generate_all(self, generation_func: Callable[[str, str, str], str]) -> dict[str, str]:
        """
        Generate all sections in parallel, respecting dependencies.

        Args:
            generation_func: Async function(section_id, title, prompt) -> content

        Returns:
            Dict mapping section_id to generated content
        """
        # Validate dependencies
        self._validate_dependencies()

        # Generate sections with dependency tracking
        while self._has_pending_sections():
            # Find sections that can run (no pending dependencies)
            ready = self._get_ready_sections()

            if not ready:
                raise RuntimeError("Circular dependency detected or no ready sections")

            # Generate up to max_concurrent sections in parallel
            tasks = []
            for section_id in ready[:self.max_concurrent]:
                section = self.sections[section_id]
                section.status = SectionStatus.IN_PROGRESS
                
                # Prepare context from dependencies
                context = self._get_section_context(section)
                
                task = self._generate_section(
                    section,
                    generation_func,
                    context,
                )
                tasks.append(task)

            # Wait for batch to complete
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Section generation error: {result}")

        return self.completed

    async def _generate_section(
        self,
        section: Section,
        generation_func: Callable,
        context: str,
    ) -> None:
        """Generate a single section."""
        try:
            # Enhance prompt with context if dependencies exist
            enhanced_prompt = section.prompt
            if context:
                enhanced_prompt = f"{enhanced_prompt}\n\nContext from previous sections:\n{context}"

            # Call generation function
            content = await self._run_async(
                generation_func,
                section.id,
                section.title,
                enhanced_prompt,
            )

            section.content = content
            section.status = SectionStatus.COMPLETED
            self.completed[section.id] = content

            logger.info(f"Completed section: {section.title}")

        except Exception as exc:
            section.status = SectionStatus.FAILED
            section.error = str(exc)
            logger.error(f"Failed to generate section {section.id}: {exc}")

    def _get_ready_sections(self) -> list[str]:
        """Get sections that are ready to generate (all dependencies completed)."""
        ready = []

        for section_id, section in self.sections.items():
            if section.status != SectionStatus.PENDING:
                continue

            # Check if all dependencies are complete
            all_deps_complete = all(
                self.sections[dep_id].status == SectionStatus.COMPLETED
                for dep_id in section.dependencies
            )

            if all_deps_complete:
                ready.append(section_id)

        return ready

    def _has_pending_sections(self) -> bool:
        """Check if there are any pending sections."""
        return any(s.status in [SectionStatus.PENDING, SectionStatus.IN_PROGRESS] for s in self.sections.values())

    def _validate_dependencies(self) -> None:
        """Validate that dependencies are valid and acyclic."""
        # Check all dependencies exist
        for section in self.sections.values():
            for dep_id in section.dependencies:
                if dep_id not in self.sections:
                    raise ValueError(f"Unknown dependency: {dep_id} for section {section.id}")

        # Check for cycles (simple DFS)
        visited = set()
        rec_stack = set()

        def has_cycle(section_id: str) -> bool:
            visited.add(section_id)
            rec_stack.add(section_id)

            for dep_id in self.sections[section_id].dependencies:
                if dep_id not in visited:
                    if has_cycle(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True

            rec_stack.remove(section_id)
            return False

        for section_id in self.sections:
            if section_id not in visited:
                if has_cycle(section_id):
                    raise ValueError("Circular dependency detected in sections")

    def _get_section_context(self, section: Section) -> str:
        """Get context from dependent sections."""
        context_parts = []

        for dep_id in section.dependencies:
            if dep_id in self.completed:
                content = self.completed[dep_id]
                # Truncate to first 500 chars to keep context manageable
                context_parts.append(f"From '{self.sections[dep_id].title}':\n{content[:500]}...")

        return "\n\n".join(context_parts)

    @staticmethod
    async def _run_async(func: Callable, *args, **kwargs):
        """Run a function asynchronously (handle both sync and async functions)."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def get_status(self) -> dict:
        """Get current generation status."""
        return {
            "sections": {
                section_id: {
                    "title": section.title,
                    "status": section.status.value,
                    "has_error": section.error is not None,
                }
                for section_id, section in self.sections.items()
            },
            "total": len(self.sections),
            "completed": len([s for s in self.sections.values() if s.status == SectionStatus.COMPLETED]),
            "failed": len([s for s in self.sections.values() if s.status == SectionStatus.FAILED]),
        }
