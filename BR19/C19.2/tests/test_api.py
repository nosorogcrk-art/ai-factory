import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_optimize_start():
    with patch("main.run_optimization", new_callable=AsyncMock):
        response = client.post("/optimize/test_prompt", json={"goals": ["reduce_errors"], "num_variants": 3})
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "started"

def test_get_optimization_status():
    response = client.get("/optimize/test_prompt/status")
    assert response.status_code == 200
    assert "jobs" in response.json()

def test_list_candidates():
    response = client.get("/candidates")
    assert response.status_code == 200
    assert "candidates" in response.json()

def test_get_job_candidates_not_found():
    response = client.get("/jobs/nonexistent/candidates")
    assert response.status_code == 404

def test_promote_candidate_not_found():
    response = client.post("/candidates/nonexistent/promote")
    assert response.status_code == 404