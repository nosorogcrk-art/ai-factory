import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("services.perform_deployment", new_callable=AsyncMock)
def test_deploy(mock_deploy):
    response = client.post("/deploy", json={"repo_url": "https://github.com/test/repo", "branch": "main"})
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "started"

def test_list_deployments():
    response = client.get("/deployments")
    assert response.status_code == 200
    assert "deployments" in response.json()

def test_deployment_status_not_found():
    response = client.get("/deployments/nonexistent/status")
    assert response.status_code == 404

@patch("services.perform_deployment", new_callable=AsyncMock)
def test_webhook(mock_deploy):
    payload = {
        "ref": "refs/heads/main",
        "repository": {"clone_url": "https://github.com/test/repo"}
    }
    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data