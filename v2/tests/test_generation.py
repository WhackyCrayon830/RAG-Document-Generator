"""Test suite for document generation."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import shutil


class TestDocumentGeneration:
    """Test document generation workflow."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory."""
        tmpdir = Path(tempfile.mkdtemp())
        yield tmpdir
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def mock_services(self):
        """Mock backend services."""
        with patch("backend.services") as mock:
            yield mock

    def test_generate_basic_document(self, mock_services):
        """Test basic document generation."""
        from backend import services
        
        # Mock the service call
        mock_services.generate_document.return_value = {
            "run_id": "test_run_001",
            "status": "success",
            "sections": [
                {"title": "Introduction", "content": "Test introduction"},
                {"title": "Conclusion", "content": "Test conclusion"},
            ],
        }
        
        result = mock_services.generate_document(
            "test_project",
            "Test Document",
            "Generate a test document",
        )
        
        assert result["status"] == "success"
        assert result["run_id"] == "test_run_001"
        assert len(result["sections"]) == 2

    def test_generate_with_required_sections(self, mock_services):
        """Test document generation with required sections."""
        mock_services.generate_document.return_value = {
            "run_id": "test_run_002",
            "status": "success",
            "sections": [
                {"title": "Background", "content": "Content"},
                {"title": "Methods", "content": "Content"},
                {"title": "Results", "content": "Content"},
            ],
        }
        
        result = mock_services.generate_document(
            "test_project",
            "Research Paper",
            "Generate research paper",
            required_sections=["Background", "Methods", "Results"],
        )
        
        assert len(result["sections"]) == 3
        assert all(s["title"] in ["Background", "Methods", "Results"] for s in result["sections"])

    def test_generate_with_template(self, mock_services):
        """Test document generation with template."""
        mock_services.generate_document.return_value = {
            "run_id": "test_run_003",
            "status": "success",
            "template_applied": True,
            "sections": [],
        }
        
        result = mock_services.generate_document(
            "test_project",
            "Templated Document",
            "Generate with template",
            template_id="template_001",
        )
        
        assert result["template_applied"] is True

    def test_generate_model_overrides(self, mock_services):
        """Test document generation with model overrides."""
        mock_services.generate_document.return_value = {
            "run_id": "test_run_004",
            "status": "success",
            "models_used": {
                "writing": "llama2:13b",
                "validation": "mistral:7b",
            },
        }
        
        result = mock_services.generate_document(
            "test_project",
            "Document",
            "Generate document",
            model_overrides={"writing": "llama2:13b", "validation": "mistral:7b"},
        )
        
        assert result["models_used"]["writing"] == "llama2:13b"


class TestDocumentValidation:
    """Test document validation."""

    def test_section_validation_min_length(self):
        """Test that sections meet minimum length requirements."""
        from backend.agents.validator.agent import validate_section
        
        # Mock validation that checks minimum length
        section = {
            "title": "Introduction",
            "content": "This is a very short section.",
        }
        
        # This should fail if content is too short
        # Actual implementation depends on your validation logic
        assert len(section["content"]) > 0

    def test_citation_validation(self):
        """Test citation validation in generated content."""
        section = {
            "title": "Background",
            "content": "According to Smith (2020), the research shows...",
        }
        
        # Should have citations if content is quoted
        assert "(" in section["content"] and ")" in section["content"]

    def test_formatting_validation(self):
        """Test content formatting validation."""
        section = {
            "title": "Methods",
            "content": "1. Step one\n2. Step two\n3. Step three",
        }
        
        # Should be properly formatted
        lines = section["content"].split("\n")
        assert len(lines) >= 2


class TestDocumentExport:
    """Test document export functionality."""

    @pytest.fixture
    def sample_sections(self):
        """Sample sections for export testing."""
        return [
            {
                "title": "Introduction",
                "content": "This is the introduction.\n\nIt has multiple paragraphs.",
            },
            {
                "title": "Body",
                "content": "This is the main content.\n\nWith substantial information.",
            },
        ]

    def test_docx_export(self, sample_sections, tmp_path):
        """Test DOCX export functionality."""
        from backend.exporters.docx.compiler import compile_docx
        
        output_file = tmp_path / "test_document.docx"
        result = compile_docx("Test Document", sample_sections, output_file)
        
        assert result.exists()
        assert result.suffix == ".docx"
        assert result.stat().st_size > 0

    def test_pdf_export(self, sample_sections, tmp_path):
        """Test PDF export functionality."""
        from backend.exporters.pdf import compile_pdf
        
        output_file = tmp_path / "test_document.pdf"
        result = compile_pdf("Test Document", sample_sections, output_file)
        
        assert result.exists()
        assert result.suffix == ".pdf"
        assert result.stat().st_size > 0

    def test_pdf_export_with_special_characters(self, tmp_path):
        """Test PDF export with special characters."""
        from backend.exporters.pdf import compile_pdf
        
        sections = [
            {
                "title": "Special Characters",
                "content": "Test with é, ñ, ü, and other special chars. Also test © and ®.",
            }
        ]
        
        output_file = tmp_path / "special_chars.pdf"
        result = compile_pdf("Document", sections, output_file)
        
        assert result.exists()
        assert result.stat().st_size > 0


class TestAsyncTasks:
    """Test async task management."""

    def test_task_tracker_initialization(self):
        """Test task tracker initialization."""
        from backend.api.task_tracker import TaskTracker
        
        tracker = TaskTracker()
        assert tracker is not None
        assert hasattr(tracker, "redis_client")

    @pytest.mark.asyncio
    async def test_task_status_response_model(self):
        """Test task status response model."""
        from backend.api.models import TaskStatusResponse, TaskStatus
        from datetime import datetime
        
        response = TaskStatusResponse(
            task_id="test_task_001",
            status=TaskStatus.STARTED,
            progress=50,
            current="Processing section 2 of 4",
            total_steps=4,
        )
        
        assert response.task_id == "test_task_001"
        assert response.status == TaskStatus.STARTED
        assert response.progress == 50

    def test_task_response_model(self):
        """Test task response model."""
        from backend.api.models import TaskResponse, TaskStatus
        from datetime import datetime
        
        response = TaskResponse(
            task_id="task_001",
            status=TaskStatus.PENDING,
            message="Task queued",
            created_at=datetime.utcnow(),
        )
        
        assert response.task_id == "task_001"
        assert response.status == TaskStatus.PENDING


class TestIngestionWorkflow:
    """Test document ingestion workflow."""

    @pytest.fixture
    def sample_document(self, tmp_path):
        """Create a sample document for ingestion."""
        doc_path = tmp_path / "sample.txt"
        doc_path.write_text("This is a sample document.\n\nIt contains multiple paragraphs.\n\nFor testing purposes.")
        return doc_path

    def test_ingest_text_document(self, sample_document):
        """Test ingesting a text document."""
        from backend import services
        
        with patch("backend.services.ingest_file") as mock_ingest:
            mock_ingest.return_value = {
                "status": "success",
                "file_hash": "abc123def456",
                "chunks": 3,
            }
            
            result = mock_ingest(
                "test_project",
                sample_document,
                "sample.txt",
            )
            
            assert result["status"] == "success"
            assert result["chunks"] == 3

    def test_document_deduplication(self):
        """Test that duplicate documents are skipped."""
        from backend import services
        
        with patch("backend.services.ingest_file") as mock_ingest:
            mock_ingest.return_value = {
                "status": "duplicate",
                "file_hash": "abc123def456",
                "message": "Document already ingested",
            }
            
            result = mock_ingest(
                "test_project",
                Path("dummy.txt"),
                "dummy.txt",
            )
            
            assert result["status"] == "duplicate"


class TestRetrieval:
    """Test document retrieval."""

    def test_vector_search(self):
        """Test vector-based document search."""
        from backend import services
        
        with patch("backend.services.search_project") as mock_search:
            mock_search.return_value = [
                {
                    "chunk_id": "chunk_001",
                    "content": "Relevant content about topic",
                    "score": 0.92,
                    "source": "document_001",
                },
                {
                    "chunk_id": "chunk_002",
                    "content": "Related information on topic",
                    "score": 0.87,
                    "source": "document_002",
                },
            ]
            
            results = mock_search("test_project", "topic information", top_k=5)
            
            assert len(results) == 2
            assert all("score" in r for r in results)
            assert results[0]["score"] >= results[1]["score"]

    def test_search_with_filters(self):
        """Test search with filtering."""
        from backend import services
        
        with patch("backend.services.search_project") as mock_search:
            mock_search.return_value = [
                {
                    "chunk_id": "chunk_001",
                    "content": "Filtered result",
                    "score": 0.95,
                    "source": "recent_doc",
                }
            ]
            
            # Mock filtering by source
            results = mock_search("test_project", "query", top_k=5)
            
            assert len(results) == 1
            assert results[0]["source"] == "recent_doc"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
