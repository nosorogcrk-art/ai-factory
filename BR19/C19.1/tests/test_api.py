import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_cluster_start():
    with patch("main._model_available", True), patch("main.is_job_running", return_value=False), patch("main.cluster_errors"):
        response = client.post("/cluster", json={
            "from_time": "2026-01-01T00:00:00Z",
            "to_time": "2026-01-02T00:00:00Z"
        })
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "started"

def test_list_clusters():
    response = client.get("/clusters")
    assert response.status_code == 200
    data = response.json()
    assert "clusters" in data

def test_get_cluster_not_found():
    response = client.get("/clusters/99999")
    assert response.status_code == 404

def test_cluster_statistics():
    response = client.get("/clusters/statistics")
    assert response.status_code == 200
    data = response.json()
    assert "total_clusters" in data

def test_pattern_analysis_start():
    with patch("main.is_job_running", return_value=False):
        response = client.post("/patterns/analyze", json={"min_support": 2})
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data