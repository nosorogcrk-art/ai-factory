import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, mock_open
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_check_and_build_queue_no_file():
    """Тест проверки очереди, когда файл не существует"""
    from api import check_and_build_queue
    
    with patch('pathlib.Path.exists') as mock_exists:
        mock_exists.return_value = False
        result = await check_and_build_queue()
        assert result["status"] == "skipped"
        assert "No queue file found" in result["message"]

@pytest.mark.asyncio
async def test_check_and_build_queue_already_processed():
    """Тест проверки очереди, когда файл уже обработан"""
    from api import check_and_build_queue
    
    # Создаем мок для Path.exists, который будет возвращать True для обоих файлов
    with patch('pathlib.Path.exists') as mock_exists:
        # exists вызывается дважды: для queue_file и processed_flag
        # Нужно, чтобы processed_flag.exists() вернул True
        # Проще всего сделать side_effect, который возвращает True для всех вызовов
        mock_exists.return_value = True
        
        result = await check_and_build_queue()
        assert result["status"] == "skipped"
        assert "Queue already processed" in result["message"]

@pytest.mark.asyncio
async def test_check_and_build_queue_success():
    """Тест успешной проверки очереди и отправки запроса"""
    from api import check_and_build_queue
    
    mock_queue_data = [
        {"container_id": "C1", "spec": {"key": "value1"}},
        {"container_id": "C2", "spec": {"key": "value2"}}
    ]
    
    # Используем side_effect как список значений: True для queue_file, False для processed_flag
    with patch('pathlib.Path.exists') as mock_exists:
        mock_exists.side_effect = [True, False]  # Первый вызов True, второй False
        
        with patch('builtins.open', mock_open(read_data='[{"container_id": "C1", "spec": {"key": "value1"}}, {"container_id": "C2", "spec": {"key": "value2"}}]')):
            with patch('json.load') as mock_json_load:
                mock_json_load.return_value = mock_queue_data
                
                mock_response = AsyncMock()
                mock_response.raise_for_status = AsyncMock()
                mock_response.status_code = 200
                
                # Мокаем httpx.AsyncClient как контекстный менеджер
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client.post = AsyncMock(return_value=mock_response)
                
                with patch('httpx.AsyncClient', return_value=mock_client):
                    with patch('pathlib.Path.touch') as mock_touch:
                        result = await check_and_build_queue()
                        assert result["status"] == "success"
                        assert "Build triggered" in result["message"]

def test_trigger_build_endpoint():
    """Тест эндпоинта /trigger_build"""
    with patch('api.check_and_build_queue', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {"status": "success", "message": "Build triggered"}
        response = client.post("/trigger_build")
        assert response.status_code == 200
        assert response.json()["status"] == "success"

def test_health_endpoint():
    """Тест эндпоинта /health"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"