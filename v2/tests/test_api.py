"""Test suite for API endpoints and async functionality."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from backend.main import app
    return TestClient(app)


class TestProjectAPIs:
    """Test project management APIs."""

    def test_list_projects(self, client):
        """Test listing projects."""
        with patch("backend.services.list_projects") as mock_list:
            mock_list.return_value = [
                {"id": "proj_001", "name": "Project 1"},
                {"id": "proj_002", "name": "Project 2"},
            ]
            
            response = client.get("/projects")
            assert response.status_code == 200
            assert len(response.json()) == 2

    def test_create_project(self, client):
        """Test creating a project."""
        with patch("backend.services.create_project") as mock_create:
            mock_create.return_value = {"id": "proj_003", "name": "New Project"}
            
            response = client.post("/projects", json={"name": "New Project"})
            assert response.status_code == 200
            assert response.json()["name"] == "New Project"

    def test_get_project(self, client):
        """Test getting a specific project."""
        with patch("backend.services.get_project") as mock_get:
            mock_get.return_value = {"id": "proj_001", "name": "Project 1"}
            
            response = client.get("/projects/proj_001")
            assert response.status_code == 200
            assert response.json()["id"] == "proj_001"

    def test_get_project_not_found(self, client):
        """Test getting non-existent project."""
        with patch("backend.services.get_project") as mock_get:
            mock_get.return_value = None
            
            response = client.get("/projects/nonexistent")
            assert response.status_code == 404


class TestAsyncAPIs:
    """Test async API endpoints."""

    def test_upload_async(self, client):
        """Test async file upload."""
        with patch("workers.celery_app.celery_app.send_task") as mock_task:
            mock_task.return_value = MagicMock(id="task_001")
            
            # Create test file
            test_file = ("test.txt", b"Test content", "text/plain")
            
            response = client.post(
                "/upload/async",
                data={"project_id": "proj_001"},
                files={"file": test_file},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "task_001"
            assert data["status"] == "pending"

    def test_generate_async(self, client):
        """Test async document generation."""
        with patch("workers.celery_app.celery_app.send_task") as mock_task:
            mock_task.return_value = MagicMock(id="task_002")
            
            payload = {
                "project_id": "proj_001",
                "title": "Test Document",
                "prompt": "Generate a test document",
            }
            
            response = client.post("/generate/async", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "task_002"
            assert data["status"] == "pending"

    def test_get_task_status(self, client):
        """Test getting task status."""
        with patch("backend.api.task_tracker.TaskTracker.get_status") as mock_status:
            from backend.api.models import TaskStatusResponse, TaskStatus
            
            mock_status.return_value = TaskStatusResponse(
                task_id="task_001",
                status=TaskStatus.STARTED,
                progress=50,
                current="Processing...",
            )
            
            response = client.get("/tasks/task_001/status")
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "task_001"
            assert data["status"] == "started"
            assert data["progress"] == 50

    def test_task_not_found(self, client):
        """Test getting status of non-existent task."""
        with patch("backend.api.task_tracker.TaskTracker.get_status") as mock_status:
            mock_status.return_value = None
            
            response = client.get("/tasks/nonexistent/status")
            assert response.status_code == 404

    def test_cancel_task(self, client):
        """Test cancelling a task."""
        with patch("workers.celery_app.celery_app.control.revoke") as mock_revoke:
            with patch("backend.api.task_tracker.TaskTracker.cancel_task") as mock_cancel:
                mock_cancel.return_value = True
                
                response = client.delete("/tasks/task_001")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "revoked"


class TestExportAPIs:
    """Test document export APIs."""

    def test_export_pdf(self, client):
        """Test PDF export endpoint."""
        with patch("backend.services.project_dir") as mock_dir:
            with patch("backend.exporters.pdf.compile_pdf") as mock_pdf:
                from pathlib import Path
                import tempfile
                
                tmpdir = Path(tempfile.mkdtemp())
                mock_dir.return_value = tmpdir
                mock_pdf.return_value = tmpdir / "test.pdf"
                
                # Create mock sections file
                import json
                (tmpdir / "runs").mkdir(exist_ok=True)
                run_file = tmpdir / "runs" / "run_001_sections.json"
                run_file.write_text(json.dumps({
                    "title": "Test Doc",
                    "sections": [{"title": "Intro", "content": "Text"}]
                }))
                
                # Create mock PDF file
                pdf_path = tmpdir / "exports" / "run_001.pdf"
                pdf_path.parent.mkdir(exist_ok=True)
                pdf_path.write_bytes(b"PDF content")
                
                response = client.post("/projects/proj_001/export/run_001/pdf")
                # Note: This might return 307 or 200 depending on FileResponse handling
                assert response.status_code in [200, 307]

    def test_download_docx(self, client):
        """Test DOCX download endpoint."""
        with patch("backend.services.project_dir") as mock_dir:
            from pathlib import Path
            import tempfile
            
            tmpdir = Path(tempfile.mkdtemp())
            mock_dir.return_value = tmpdir
            
            # Create mock DOCX file
            docx_path = tmpdir / "generated" / "run_001.docx"
            docx_path.parent.mkdir(parents=True, exist_ok=True)
            docx_path.write_bytes(b"DOCX content")
            
            response = client.get("/download/proj_001/run_001")
            assert response.status_code in [200, 307]


class TestSearchAPIs:
    """Test search and retrieval APIs."""

    def test_search_project(self, client):
        """Test project search."""
        with patch("backend.services.search_project") as mock_search:
            mock_search.return_value = [
                {
                    "chunk_id": "chunk_001",
                    "content": "Relevant result",
                    "score": 0.95,
                }
            ]
            
            payload = {
                "project_id": "proj_001",
                "query": "test query",
                "top_k": 5,
            }
            
            response = client.post("/retrieval/search", json=payload)
            assert response.status_code == 200
            results = response.json()
            assert len(results) == 1
            assert results[0]["score"] == 0.95


class TestModelAPIs:
    """Test model configuration APIs."""

    def test_get_model_settings(self, client):
        """Test getting model settings."""
        with patch("backend.services.get_model_config") as mock_get:
            mock_get.return_value = {
                "embedding_model": "nomic-embed-text",
                "planning_model": "mistral",
                "writing_model": "llama2",
            }
            
            response = client.get("/settings/models")
            assert response.status_code == 200
            data = response.json()
            assert "embedding_model" in data

    def test_save_model_settings(self, client):
        """Test saving model settings."""
        with patch("backend.services.save_model_config") as mock_save:
            mock_save.return_value = {"status": "saved"}
            
            payload = {
                "embedding_model": "nomic-embed-text",
                "planning_model": "mistral",
            }
            
            response = client.post("/settings/models", json=payload)
            assert response.status_code == 200


class TestOllamaAPIs:
    """Test Ollama integration APIs."""

    def test_list_ollama_models(self, client):
        """Test listing available Ollama models."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "models": [
                    {"name": "llama2"},
                    {"name": "mistral"},
                ]
            }
            mock_get.return_value = mock_response
            
            response = client.get("/ollama/models")
            assert response.status_code == 200
            data = response.json()
            assert data["available"] is True
            assert "models" in data

    def test_pull_ollama_model(self, client):
        """Test pulling an Ollama model."""
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "success"}
            mock_post.return_value = mock_response
            
            response = client.post("/ollama/pull", json={"model": "llama2"})
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
