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


def test_package_tz_format_success():
    """Тест нового формата ТЗ с project_id и files."""
    with patch("services.create_archive") as mock_create_archive:
        mock_create_archive.return_value = "01_ЦЕХ/ПРОДУКТЫ/test_proj_20250411_091500.zip"
        response = client.post("/package", json={
            "project_id": "test_proj",
            "files": [
                {"filename": "test.txt", "content": "Hello"},
                {"filename": "main.py", "content": "print(1)"}
            ]
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "archive_path" in data
        assert "download_url" in data
        assert data["archive_path"] == "01_ЦЕХ/ПРОДУКТЫ/test_proj_20250411_091500.zip"


def test_package_tz_format_empty_files():
    """Тест нового формата ТЗ с пустым списком файлов."""
    response = client.post("/package", json={
        "project_id": "test_proj",
        "files": []
    })
    assert response.status_code == 400
    assert "No files provided" in response.text


def test_package_tz_format_failure():
    """Тест нового формата ТЗ с ошибкой в сервисе."""
    with patch("services.create_archive") as mock_create_archive:
        mock_create_archive.side_effect = Exception("Test error")
        response = client.post("/package", json={
            "project_id": "test_proj",
            "files": [
                {"filename": "test.txt", "content": "Hello"}
            ]
        })
        assert response.status_code == 500
        assert "Test error" in response.text
