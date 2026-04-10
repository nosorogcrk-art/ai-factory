import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_build_from_queue_missing_queue():
    """Тест эндпоинта /build_from_queue без поля queue"""
    response = client.post("/build_from_queue", json={})
    assert response.status_code == 400
    assert "Missing 'queue' field" in response.json()["detail"]

def test_build_from_queue_empty_queue():
    """Тест эндпоинта /build_from_queue с пустой очередью"""
    response = client.post("/build_from_queue", json={"queue": []})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["result"]["total"] == 0

@pytest.mark.asyncio
async def test_build_from_queue_success():
    """Тест успешной сборки из очереди"""
    from services import build_from_queue
    
    mock_queue = [
        {"container_id": "C1", "spec": {"key": "value1"}},
        {"container_id": "C2", "spec": {"key": "value2"}}
    ]
    
    mock_files = [
        {"path": "main.py", "content": "print('hello')"},
        {"path": "utils.py", "content": "def helper(): pass"}
    ]
    
    with patch('services.generate_code_from_l5', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = mock_files
        
        result = await build_from_queue(mock_queue)
        
        assert result["total"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["container_id"] == "C1"
        assert result["results"][0]["status"] == "success"
        assert result["results"][0]["files"] == mock_files
        assert result["results"][1]["container_id"] == "C2"
        assert result["results"][1]["status"] == "success"

@pytest.mark.asyncio
async def test_build_from_queue_missing_fields():
    """Тест сборки из очереди с отсутствующими полями"""
    from services import build_from_queue
    
    mock_queue = [
        {"container_id": "C1"},  # нет spec
        {"spec": {"key": "value"}}  # нет container_id
    ]
    
    result = await build_from_queue(mock_queue)
    
    assert result["total"] == 2
    assert result["results"][0]["error"] == "Missing container_id or spec in queue item"
    assert result["results"][1]["error"] == "Missing container_id or spec in queue item"

@pytest.mark.asyncio
async def test_build_from_queue_generation_error():
    """Тест сборки из очереди с ошибкой генерации"""
    from services import build_from_queue
    
    mock_queue = [
        {"container_id": "C1", "spec": {"key": "value1"}}
    ]
    
    with patch('services.generate_code_from_l5', new_callable=AsyncMock) as mock_generate:
        mock_generate.side_effect = Exception("Generation failed")
        
        result = await build_from_queue(mock_queue)
        
        assert result["total"] == 1
        assert result["results"][0]["container_id"] == "C1"
        assert result["results"][0]["status"] == "error"
        assert "Generation failed" in result["results"][0]["error"]

def test_build_from_queue_endpoint_success():
    """Тест эндпоинта /build_from_queue с успешной сборкой"""
    mock_queue = [
        {"container_id": "C1", "spec": {"key": "value1"}}
    ]
    
    mock_result = {
        "total": 1,
        "results": [
            {"container_id": "C1", "status": "success", "files": [{"path": "main.py", "content": "code"}]}
        ]
    }
    
    with patch('services.build_from_queue', new_callable=AsyncMock) as mock_build:
        mock_build.return_value = mock_result
        
        response = client.post("/build_from_queue", json={"queue": mock_queue})
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["result"]["total"] == 1
        assert response.json()["result"]["results"][0]["container_id"] == "C1"

def test_health_endpoint():
    """Тест эндпоинта /health"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"