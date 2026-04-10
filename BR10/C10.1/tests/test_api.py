import sys
from pathlib import Path

# Добавляем путь к папке контейнера C10.1, чтобы импортировать main и services
sys.path.insert(0, str(Path(__file__).parent.parent))

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


def test_generate_from_l5_endpoint_missing_params():
    """Тест эндпоинта /generate-from-l5 с отсутствующими параметрами"""
    response = client.post("/generate-from-l5", json={})
    # FastAPI возвращает 422 при ошибках валидации Pydantic
    assert response.status_code == 422
    # Проверяем, что есть детали ошибки
    assert "detail" in response.json()


def test_generate_from_l5_endpoint_success(mocker):
    """Тест успешной генерации через /generate-from-l5"""
    mock_files = [{"path": "main.py", "content": "print('ok')"}]
    
    async def mock_generate(*args, **kwargs):
        return mock_files
    
    mocker.patch("services.generate_code_from_l5", mock_generate)
    
    response = client.post("/generate-from-l5", json={
        "container_id": "c1",
        "spec": {"name": "Test Container", "dependencies": ["fastapi"]}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["files"]) == 1
    assert data["files"][0]["path"] == "main.py"
    assert data["files"][0]["content"] == "print('ok')"


def test_generate_from_l5_endpoint_error(mocker):
    """Тест ошибки генерации через /generate-from-l5"""
    async def mock_generate(*args, **kwargs):
        raise Exception("Generation failed")
    
    mocker.patch("services.generate_code_from_l5", mock_generate)
    
    response = client.post("/generate-from-l5", json={
        "container_id": "c1",
        "spec": {"name": "Test Container"}
    })
    assert response.status_code == 500
    assert "Generation failed" in response.json()["detail"]
