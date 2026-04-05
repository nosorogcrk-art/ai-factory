from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_package_success():
    with patch("services.package") as mock_package:
        mock_package.return_value = (True, "/path/to/archive.tar.gz")
        response = client.post("/package", json={
            "repo_path": "/app/02_ПРОДУКТ/РЕПО",
            "version": "v1.0.0",
            "skills": ["SKILL-001"]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["archive"] == "/path/to/archive.tar.gz"

def test_package_failure():
    with patch("services.package") as mock_package:
        mock_package.return_value = (False, "Some error")
        response = client.post("/package", json={
            "repo_path": "/app/02_ПРОДУКТ/РЕПО",
            "version": "v1.0.0"
        })
        assert response.status_code == 500
        assert "Some error" in response.text