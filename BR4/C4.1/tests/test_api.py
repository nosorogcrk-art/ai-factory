from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_status_success():
    with patch("services.aggregate_status", new_callable=AsyncMock) as mock_agg:
        mock_agg.return_value = {
            "metrics": {"cpu": 10},
            "branches": [],
            "tasks": [],
            "skill_stats": {"total": 0, "active": 0},
            "last_update": "2026-03-26T00:00:00"
        }
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "branches" in data

def test_status_error_fallback():
    with patch("services.aggregate_status", side_effect=Exception("DB error")):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["metrics"] == {}
        assert data["branches"] == []