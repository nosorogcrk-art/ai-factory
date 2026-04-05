import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_dialog_missing_project_id():
    response = client.post("/api/dialog", json={"message": "Hello"})
    assert response.status_code == 422


def test_dialog_success(mocker):
    mocker.patch("services.process_dialog", return_value=("✅ Задача сформирована! ID: DIALOG-123", True, "DIALOG-123", {}))
    response = client.post("/api/dialog", json={"project_id": "proj_123", "message": "Сделай задачу"})
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "proj_123"
    assert data["completed"] is True
    assert data["task_id"] == "DIALOG-123"


def test_dialog_triggers_background_task(mocker):
    mock_processing = mocker.patch("services.background_processing")
    mocker.patch("services.process_dialog", return_value=("✅ Задача", True, "DIALOG-123", {"title": "Test"}))
    response = client.post("/api/dialog", json={"project_id": "proj_123", "message": "Сделай"})
    assert response.status_code == 200
    mock_processing.assert_called_once_with("proj_123", {"title": "Test"}, "DIALOG-123")