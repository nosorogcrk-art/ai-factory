import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from services import generate_code_from_patches

@pytest.mark.asyncio
async def test_generate_code_from_patches_fallback():
    """Тест fallback, когда навык недоступен"""
    # Мокаем весь AsyncClient, чтобы он выбрасывал исключение
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post.side_effect = Exception("Skill unavailable")
    
    with patch("services.httpx.AsyncClient", return_value=mock_client):
        files = await generate_code_from_patches("test", ["P1"])
        assert len(files) == 1
        assert files[0]["filename"] == "main.py"
        assert "FastAPI" in files[0]["content"]
        assert "@app.get('/hello')" in files[0]["content"]

@pytest.mark.asyncio
async def test_generate_code_from_patches_success():
    """Тест успешной генерации кода через навык"""
    # Создаем мок ответа
    mock_response = AsyncMock()
    mock_response.status_code = 200
    # json() должен возвращать корутину, которая возвращает словарь
    mock_response.json.return_value = {
        "result": {
            "files": [
                {"filename": "main.py", "content": "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/hello')\nasync def hello():\n    return {'message': 'Hello, World!'}\n"},
                {"filename": "requirements.txt", "content": "fastapi==0.104.1\nuvicorn==0.24.0\n"}
            ]
        }
    }
    
    # Мокаем AsyncClient
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post.return_value = mock_response
    
    with patch("services.httpx.AsyncClient", return_value=mock_client):
        files = await generate_code_from_patches("test", ["P1"])
        assert len(files) == 2
        assert files[0]["filename"] == "main.py"
        assert "FastAPI" in files[0]["content"]
        assert files[1]["filename"] == "requirements.txt"
        assert "fastapi" in files[1]["content"]

@pytest.mark.asyncio
async def test_generate_code_from_patches_empty_patch_ids():
    """Тест с пустым списком патчей"""
    files = await generate_code_from_patches("test", [])
    assert len(files) == 1
    assert files[0]["filename"] == "main.py"
    assert "FastAPI" in files[0]["content"]

@pytest.mark.asyncio
async def test_generate_code_from_patches_skill_error():
    """Тест, когда навык возвращает ошибку"""
    # Создаем мок ответа с ошибкой
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "error": "Generation failed"
        }
    }
    
    # Мокаем AsyncClient
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post.return_value = mock_response
    
    with patch("services.httpx.AsyncClient", return_value=mock_client):
        files = await generate_code_from_patches("test", ["P1"])
        # Должен вернуться fallback
        assert len(files) == 1
        assert files[0]["filename"] == "main.py"
        assert "FastAPI" in files[0]["content"]

@pytest.mark.asyncio
async def test_generate_code_from_patches_http_error():
    """Тест HTTP ошибки при вызове навыка"""
    # Мокаем AsyncClient, чтобы он выбрасывал исключение при raise_for_status
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = Exception("HTTP 500")
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post.return_value = mock_response
    
    with patch("services.httpx.AsyncClient", return_value=mock_client):
        files = await generate_code_from_patches("test", ["P1"])
        # Должен вернуться fallback
        assert len(files) == 1
        assert files[0]["filename"] == "main.py"
        assert "FastAPI" in files[0]["content"]
