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

def test_package_new_format_with_files():
    with patch("services.package_code") as mock_package_code:
        mock_package_code.return_value = {
            "status": "success",
            "artifact_url": "/artifacts/test.zip",
            "version": "20250410_034500"
        }
        response = client.post("/package", json={
            "files": [
                {"path": "main.py", "content": "print('hello')"},
                {"path": "utils.py", "content": "def foo(): pass"}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["artifact_url"] == "/artifacts/test.zip"
        assert "version" in data

def test_package_new_format_with_source_dir():
    with patch("services.package_code") as mock_package_code:
        mock_package_code.return_value = {
            "status": "success",
            "artifact_url": "/artifacts/test.zip",
            "version": "20250410_034500"
        }
        response = client.post("/package", json={
            "source_dir": "/tmp/source"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

def test_package_new_format_missing_params():
    response = client.post("/package", json={})
    assert response.status_code == 400
    assert "Empty request" in response.text

def test_package_code_endpoint():
    with patch("services.package_code") as mock_package_code:
        mock_package_code.return_value = {
            "status": "success",
            "artifact_url": "/artifacts/test.zip",
            "version": "20250410_034500"
        }
        response = client.post("/package_code", json={
            "files": [
                {"path": "main.py", "content": "print('hello')"}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["artifact_url"] == "/artifacts/test.zip"
