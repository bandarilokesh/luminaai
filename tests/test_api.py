import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "PaperMind AI"}

def test_system_status_endpoint():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "app_name" in data
    assert "gpu_available" in data
    assert "ollama_running" in data
    assert "total_papers" in data

def test_list_papers_endpoint():
    response = client.get("/api/papers/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_delete_nonexistent_paper():
    # Attempting to delete a paper that doesn't exist should fail with 404
    response = client.delete("/api/papers/nonexistent_paper_id_123")
    assert response.status_code == 404
