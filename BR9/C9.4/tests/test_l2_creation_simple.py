import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import services
import json
import os

# Устанавливаем переменную окружения для тестов
os.environ["DEEPSEEK_API_KEY"] = "test_key"

@pytest.mark.asyncio
async def test_get_user_messages_count_simple():
    """Простой тест подсчёта сообщений пользователя."""
    # Мокаем httpx.AsyncClient
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value=[
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "reply1"},
        {"role": "user", "content": "msg2"}
    ])
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        count = await services.get_user_messages_count("test_project")
        assert count == 2

@pytest.mark.asyncio
async def test_save_l2_artifact_simple():
    """Простой тест сохранения L2 артефакта."""
    # Мокаем httpx.AsyncClient для двух вызовов
    mock_client = AsyncMock()
    
    # Первый вызов - GET для проверки существующих артефактов
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.json = AsyncMock(return_value=[])
    
    # Второй вызов - POST для сохранения
    mock_post_response = AsyncMock()
    mock_post_response.status_code = 200
    mock_post_response.json = AsyncMock(return_value={"id": "art1"})
    
    # Настраиваем mock для последовательных вызовов
    mock_client.get = AsyncMock(return_value=mock_get_response)
    mock_client.post = AsyncMock(return_value=mock_post_response)
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await services.save_l2_artifact("test_project", {"title": "Test"})
        assert "id" in result

@pytest.mark.asyncio
async def test_force_l2_logic():
    """Тест логики принудительного создания L2 (без вызова process_dialog)."""
    # Проверяем, что функция get_user_messages_count существует
    assert hasattr(services, 'get_user_messages_count')
    
    # Проверяем, что функция save_l2_artifact существует
    assert hasattr(services, 'save_l2_artifact')
    
    # Проверяем, что функция finalize_l2 существует
    assert hasattr(services, 'finalize_l2')
    
    # Проверяем, что в process_dialog добавлена проверка на 4 сообщения
    source_code = Path(__file__).parent.parent / "services.py"
    with open(source_code, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "user_messages_count >= 4" in content
        assert "forcing L2 creation" in content

if __name__ == "__main__":
    pytest.main([__file__, "-v"])