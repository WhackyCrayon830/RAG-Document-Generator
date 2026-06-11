"""Test suite for parallel section generation and streaming."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestParallelGeneration:
    """Test parallel section generation with dependencies."""

    @pytest.mark.asyncio
    async def test_simple_parallel_generation(self):
        """Test generating independent sections in parallel."""
        from backend.orchestration.parallel_generation import SectionGenerationOrchestrator

        orchestrator = SectionGenerationOrchestrator(max_concurrent=2)
        
        # Add sections with no dependencies
        orchestrator.add_section("intro", "Introduction", "Write intro")
        orchestrator.add_section("body", "Body", "Write body")
        orchestrator.add_section("conclusion", "Conclusion", "Write conclusion")

        # Mock generation function
        async def mock_generate(section_id: str, title: str, prompt: str) -> str:
            await asyncio.sleep(0.01)
            return f"Generated content for {title}"

        result = await orchestrator.generate_all(mock_generate)

        assert len(result) == 3
        assert all(section_id in result for section_id in ["intro", "body", "conclusion"])

    @pytest.mark.asyncio
    async def test_generation_with_dependencies(self):
        """Test section generation respecting dependencies."""
        from backend.orchestration.parallel_generation import SectionGenerationOrchestrator

        orchestrator = SectionGenerationOrchestrator()
        
        # Add sections with dependencies
        orchestrator.add_section("intro", "Introduction", "Write intro")
        orchestrator.add_section("background", "Background", "Write background", dependencies=["intro"])
        orchestrator.add_section("methods", "Methods", "Write methods", dependencies=["background"])

        order = []

        async def mock_generate(section_id: str, title: str, prompt: str) -> str:
            order.append(section_id)
            await asyncio.sleep(0.01)
            return f"Content for {title}"

        result = await orchestrator.generate_all(mock_generate)

        # Verify dependency order
        intro_idx = order.index("intro")
        bg_idx = order.index("background")
        methods_idx = order.index("methods")
        
        assert intro_idx < bg_idx < methods_idx

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self):
        """Test detection of circular dependencies."""
        from backend.orchestration.parallel_generation import SectionGenerationOrchestrator

        orchestrator = SectionGenerationOrchestrator()
        
        orchestrator.add_section("a", "Section A", "Prompt", dependencies=["b"])
        orchestrator.add_section("b", "Section B", "Prompt", dependencies=["a"])

        async def mock_generate(section_id: str, title: str, prompt: str) -> str:
            return f"Content for {title}"

        with pytest.raises(ValueError, match="Circular dependency"):
            await orchestrator.generate_all(mock_generate)

    @pytest.mark.asyncio
    async def test_generation_error_handling(self):
        """Test handling of generation errors."""
        from backend.orchestration.parallel_generation import SectionGenerationOrchestrator

        orchestrator = SectionGenerationOrchestrator()
        
        orchestrator.add_section("section1", "Section 1", "Prompt")
        orchestrator.add_section("section2", "Section 2", "Prompt")

        async def mock_generate(section_id: str, title: str, prompt: str) -> str:
            if section_id == "section1":
                raise RuntimeError("Generation failed")
            return "Content"

        result = await orchestrator.generate_all(mock_generate)

        # Verify partial results
        assert "section2" in result
        assert orchestrator.sections["section1"].error is not None


class TestGenerationStreaming:
    """Test streaming generation updates."""

    def test_stream_manager_basic(self):
        """Test basic stream manager functionality."""
        from backend.streaming import GenerationStreamManager, GenerationEventType, GenerationEvent
        from datetime import datetime

        manager = GenerationStreamManager()
        
        event = GenerationEvent(
            type=GenerationEventType.STARTED,
            task_id="task_001",
            timestamp=datetime.utcnow(),
            progress=0,
            message="Starting generation",
        )
        
        # Store would happen in emit_event
        assert event.task_id == "task_001"
        assert event.type == GenerationEventType.STARTED

    @pytest.mark.asyncio
    async def test_stream_manager_event_emission(self):
        """Test event emission to listeners."""
        from backend.streaming import GenerationStreamManager, GenerationEventType, GenerationEvent
        from datetime import datetime

        manager = GenerationStreamManager()
        
        received_events = []

        async def listener(event: GenerationEvent):
            received_events.append(event)

        task_id = "task_001"
        manager.register_listener(task_id, listener)

        event = GenerationEvent(
            type=GenerationEventType.STARTED,
            task_id=task_id,
            timestamp=datetime.utcnow(),
            progress=0,
            message="Starting",
        )

        await manager.emit_event(event)

        assert len(received_events) == 1
        assert received_events[0].task_id == task_id

    def test_stream_manager_history(self):
        """Test event history tracking."""
        from backend.streaming import GenerationStreamManager, GenerationEventType, GenerationEvent
        from datetime import datetime

        manager = GenerationStreamManager()
        task_id = "task_001"

        # Simulate adding events directly
        event = GenerationEvent(
            type=GenerationEventType.STARTED,
            task_id=task_id,
            timestamp=datetime.utcnow(),
            progress=0,
            message="Starting",
        )
        
        if task_id not in manager.event_history:
            manager.event_history[task_id] = []
        manager.event_history[task_id].append(event)

        history = manager.get_history(task_id)
        
        assert len(history) == 1
        assert history[0]["task_id"] == task_id


class TestStreamingAPIs:
    """Test streaming API endpoints."""

    def test_event_history_endpoint(self):
        """Test retrieving event history."""
        from backend.api.routes.streaming import get_event_history
        from backend.streaming import get_stream_manager, GenerationEvent, GenerationEventType
        from datetime import datetime

        manager = get_stream_manager()
        task_id = "test_task_001"

        # Add some events
        event = GenerationEvent(
            type=GenerationEventType.STARTED,
            task_id=task_id,
            timestamp=datetime.utcnow(),
            progress=0,
            message="Test event",
        )
        
        if task_id not in manager.event_history:
            manager.event_history[task_id] = []
        manager.event_history[task_id].append(event)

        history = get_event_history(task_id)
        
        assert len(history) == 1
        assert history[0]["task_id"] == task_id

    def test_clear_event_history(self):
        """Test clearing event history."""
        from backend.api.routes.streaming import clear_event_history
        from backend.streaming import get_stream_manager

        manager = get_stream_manager()
        task_id = "test_task_002"

        # Add a dummy event
        if task_id not in manager.event_history:
            manager.event_history[task_id] = []
        manager.event_history[task_id].append(None)

        result = clear_event_history(task_id)

        assert result["status"] == "cleared"
        assert len(manager.event_history.get(task_id, [])) == 0


class TestBackupAndCleanup:
    """Test backup and cleanup functionality."""

    def test_backup_manager_init(self):
        """Test backup manager initialization."""
        from backend.operations import BackupManager
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BackupManager(storage_root=Path(tmpdir))
            assert manager.backup_dir.exists()

    def test_cleanup_manager_stats(self):
        """Test getting storage statistics."""
        from backend.operations import CleanupManager
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CleanupManager(storage_root=Path(tmpdir))
            stats = manager.get_storage_stats()
            
            assert "total_size_mb" in stats
            assert "projects" in stats
            assert stats["total_size_mb"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
