import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_status():
    response = client.get("/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_test_skill_not_found(monkeypatch):
    async def mock_get_skill(*args, **kwargs):
        return None
    monkeypatch.setattr("services.get_skill_from_registry", mock_get_skill)
    response = client.post("/test/SKILL-999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_test_skill_success_with_mock(monkeypatch):
    async def mock_get_skill(*args, **kwargs):
        return {"id": "SKILL-001", "name": "Test Skill", "instruction": "def run_skill(x): return {'passed': True, 'output': 'ok'}"}
    async def mock_run_docker(*args, **kwargs):
        return (True, "ok", 0.5)
    mock_send_log = AsyncMock()
    monkeypatch.setattr("services.get_skill_from_registry", mock_get_skill)
    monkeypatch.setattr("services.run_test_in_docker", mock_run_docker)
    monkeypatch.setattr("services.send_log_to_br18", mock_send_log)
    response = client.post("/test/SKILL-001")
    assert response.status_code == 200
    data = response.json()
    assert "test_run_id" in data
    assert data["skill_id"] == "SKILL-001"
    assert data["status"] == "completed"
    assert data["passed"] is True
    assert data["output"] == "ok"
    assert data["duration_seconds"] == 0.5
    mock_send_log.assert_called_once()

def test_get_results(monkeypatch):
    def mock_get_results(*args, **kwargs):
        return {
            "skill_id": "SKILL-001",
            "last_test": "2026-04-03T12:00:00",
            "overall": "passed",
            "tests": [{"name": "basic_case", "passed": True, "duration_ms": 100, "error": None}],
            "metrics": {"total_tests": 1, "passed_tests": 1}
        }
    monkeypatch.setattr("services.get_results", mock_get_results)
    response = client.get("/results/SKILL-001")
    assert response.status_code == 200
    data = response.json()
    assert data["skill_id"] == "SKILL-001"
    assert data["overall"] == "passed"
    assert "metrics" in data
    assert data["metrics"]["total_tests"] == 1

@pytest.mark.skip(reason="Requires real Docker environment")
def test_real_docker_test(monkeypatch):
    async def mock_get_skill(*args, **kwargs):
        return {
            "id": "SKILL-042",
            "name": "Dummy",
            "instruction": "def run_skill(x): return {'passed': True, 'output': 'Hello from Docker'}"
        }
    monkeypatch.setattr("services.get_skill_from_registry", mock_get_skill)
    response = client.post("/test/SKILL-042")
    assert response.status_code == 200
    data = response.json()
    assert "test_run_id" in data
    assert data["passed"] is True