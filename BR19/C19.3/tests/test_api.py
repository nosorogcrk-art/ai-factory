import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_improve_skill_start():
    with patch("main.run_improvement", new_callable=AsyncMock), \
         patch("main.fetch_skill", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {"id": "SKILL-001", "version": "1.0.0"}
        response = client.post("/skills/SKILL-001/improve", json={"goals": ["fix_errors"], "num_variants": 1})
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "started"

def test_get_job_status_not_found():
    response = client.get("/improvement_jobs/nonexistent")
    assert response.status_code == 404

def test_list_proposals():
    response = client.get("/improvement_proposals")
    assert response.status_code == 200
    assert "proposals" in response.json()

def test_cancel_job_not_found():
    response = client.post("/improvement_jobs/nonexistent/cancel")
    assert response.status_code == 404

def test_approve_proposal_not_found():
    response = client.post("/improvement_proposals/nonexistent/approve")
    assert response.status_code == 404