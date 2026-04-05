import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
import repositories as cache_repo

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_status():
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "cache_stats" in data

@patch("services.fetch_skill_from_registry", new_callable=AsyncMock)
def test_get_skill_success(mock_fetch):
    mock_fetch.return_value = {
        "id": "SKILL-001", "name": "Test", "version": "1.0",
        "instruction": "test", "depends_on": [], "allowed_for_swarm": False,
        "tags": [], "task_types": [], "languages": [], "status": "active",
        "author": "test", "description": "desc",
        "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"
    }
    response = client.get("/skill/SKILL-001")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "SKILL-001"

@patch("services.fetch_skill_from_registry", new_callable=AsyncMock)
def test_get_skill_not_found(mock_fetch):
    mock_fetch.return_value = None
    response = client.get("/skill/SKILL-999")
    assert response.status_code == 404

@patch("services.fetch_skill_from_version_control", new_callable=AsyncMock)
def test_get_skill_with_version(mock_fetch):
    mock_fetch.return_value = {
        "id": "SKILL-001", "name": "Test", "version": "1.0",
        "instruction": "test", "depends_on": [], "allowed_for_swarm": False,
        "tags": [], "task_types": [], "languages": [], "status": "active",
        "author": "test", "description": "desc",
        "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"
    }
    response = client.get("/skill/SKILL-001?version=abc123")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "SKILL-001"

@patch("services.get_skill", new_callable=AsyncMock)
def test_batch_request(mock_get_skill):
    mock_get_skill.side_effect = [
        {"id": "SKILL-001", "instruction": "test1"},
        None
    ]
    response = client.post("/skills/batch", json={"skills": ["SKILL-001", "SKILL-002"], "agent_type": "main"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0] is not None
    assert data[1] is None

def test_cache_hit():
    # Очищаем кэш перед тестом
    cache_repo.cache.clear()
    # Мокаем fetch_skill_from_registry, чтобы он возвращал данные
    with patch("services.fetch_skill_from_registry", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = {
            "id": "SKILL-001", "name": "Test", "version": "1.0",
            "instruction": "test", "depends_on": [], "allowed_for_swarm": False,
            "tags": [], "task_types": [], "languages": [], "status": "active",
            "author": "test", "description": "desc",
            "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"
        }
        response1 = client.get("/skill/SKILL-001")
        assert response1.status_code == 200
        # Первый запрос должен вызвать fetch_skill_from_registry
        mock_fetch.assert_called_once_with("SKILL-001")
        mock_fetch.reset_mock()
        response2 = client.get("/skill/SKILL-001")
        assert response2.status_code == 200
        # Второй запрос не должен вызывать fetch_skill_from_registry (кэш)
        mock_fetch.assert_not_called()