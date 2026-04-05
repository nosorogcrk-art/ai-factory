from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_command_take_success():
    with patch("services.call_handover", new_callable=AsyncMock) as mock_handover:
        mock_handover.return_value = {"status": "ok"}
        response = client.post("/api/command", json={"command": "take 123"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "taken" in data["output"]

def test_command_take_error():
    with patch("services.call_handover", new_callable=AsyncMock) as mock_handover:
        mock_handover.return_value = {"error": "Task not found"}
        response = client.post("/api/command", json={"command": "take 999"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Task not found" in data["output"]

def test_command_unknown():
    response = client.post("/api/command", json={"command": "unknown"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Unknown command" in data["output"]

def test_empty_command():
    response = client.post("/api/command", json={"command": ""})
    assert response.status_code == 400