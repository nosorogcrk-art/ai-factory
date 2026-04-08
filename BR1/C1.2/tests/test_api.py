from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_decompose_success(mocker):
    mock_service = mocker.patch("services.decompose_task", return_value=["IMP-20260324-001", "IMP-20260324-002"])
    payload = {"description": "Нужно улучшить логирование", "context": {"task_id": "TEST-123"}}
    response = client.post("/decompose", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["patches"] == ["IMP-20260324-001", "IMP-20260324-002"]
    assert data["status"] == "ok"
    mock_service.assert_called_once_with("Нужно улучшить логирование", {"task_id": "TEST-123"})


def test_decompose_empty_description():
    payload = {"description": "", "context": {}}
    response = client.post("/decompose", json=payload)
    # Pydantic валидация возвращает 422, а не 400
    assert response.status_code == 422


def test_decompose_service_error(mocker):
    mocker.patch("services.decompose_task", side_effect=Exception("Service error"))
    payload = {"description": "Test", "context": {}}
    response = client.post("/decompose", json=payload)
    assert response.status_code == 500
    assert "Internal error" in response.text


def test_decompose_with_skills(mocker):
    """Тест, что при декомпозиции учитываются навыки (косвенно через возвращаемые ID)."""
    mock_service = mocker.patch("services.decompose_task", return_value=["IMP-20260324-001"])
    payload = {"description": "Рефакторинг API", "context": {"priority": "high"}}
    response = client.post("/decompose", json=payload)
    assert response.status_code == 200
    mock_service.assert_called_once_with("Рефакторинг API", {"priority": "high"})


def test_no_api_decompose_endpoint():
    """Убедимся, что эндпоинт /api/decompose больше не существует."""
    response = client.post("/api/decompose", json={"description": "test"})
    assert response.status_code == 404  # Not Found