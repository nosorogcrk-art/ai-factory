import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

@patch("services.check_docker_socket")
@patch("services.run_tests_async", new_callable=AsyncMock)
def test_run_tests_success(mock_run, mock_check):
    mock_check.return_value = True
    with patch("pathlib.Path.exists", return_value=True):
        response = client.post("/run", json={
            "product_path": "/tmp/test_product",
            "test_suite": "tests",
            "image": "python:3.12-slim",
            "timeout_seconds": 600
        })
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

def test_run_tests_invalid_product_path():
    with patch("pathlib.Path.exists", return_value=False):
        response = client.post("/run", json={
            "product_path": "/nonexistent",
            "test_suite": "tests"
        })
        assert response.status_code == 422

def test_get_results_not_found():
    response = client.get("/results/unknown")
    assert response.status_code == 404