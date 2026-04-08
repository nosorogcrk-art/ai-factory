from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_build_success(mocker):
    mocker.patch("services.build_patches", return_value=(True, "Build started"))
    response = client.post("/build", json={"task_id": "DIALOG-123", "patch_ids": ["IMP-001"], "check_skills": True, "run_tests": True})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"


def test_build_failure(mocker):
    mocker.patch("services.build_patches", return_value=(False, "Something went wrong"))
    response = client.post("/build", json={"task_id": "DIALOG-123", "patch_ids": ["IMP-001"], "check_skills": True, "run_tests": True})
    assert response.status_code == 500
    assert "Something went wrong" in response.text


def test_generate_success():
    """Тест успешной генерации (заглушка)"""
    response = client.post("/generate", json={
        "spec_path": "/path/to/spec.md",
        "spec_content": "Test specification content"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "generated"
    assert "Code generation not yet implemented" in data["message"]
    assert data["files"] == []


def test_generate_missing_spec():
    """Тест ошибки при отсутствии спецификации"""
    response = client.post("/generate", json={
        "spec_path": "/nonexistent/path/spec.md",
        "spec_content": None
    })
    assert response.status_code == 404
    assert "Specification not found" in response.text


def test_generate_with_content_only():
    """Тест генерации только с содержимым (без файла)"""
    response = client.post("/generate", json={
        "spec_path": "/nonexistent/path/spec.md",
        "spec_content": "Test specification content"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "generated"
