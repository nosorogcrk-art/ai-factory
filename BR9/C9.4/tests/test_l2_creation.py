import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
import services
import json
import os

# Устанавливаем переменную окружения для тестов
os.environ["DEEPSEEK_API_KEY"] = "test_key"

@pytest.mark.asyncio
async def test_get_user_messages_count():
    """Тест подсчёта сообщений пользователя."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value=[
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "reply1"},
        {"role": "user", "content": "msg2"},
        {"role": "user", "content": "msg3"}
    ])
    
    # Создаем mock для httpx.AsyncClient
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        count = await services.get_user_messages_count("test_project")
        assert count == 3

@pytest.mark.asyncio
async def test_get_user_messages_count_empty():
    """Тест подсчёта сообщений пользователя при пустой истории."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        count = await services.get_user_messages_count("test_project")
        assert count == 0

@pytest.mark.asyncio
async def test_get_user_messages_count_error():
    """Тест обработки ошибки при подсчёте сообщений."""
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection error")):
        count = await services.get_user_messages_count("test_project")
        assert count == 0  # Должен вернуть 0 при ошибке

@pytest.mark.asyncio
async def test_save_l2_artifact():
    """Тест сохранения L2 артефакта."""
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.json.return_value = []  # Нет существующих артефактов
    
    mock_post_response = AsyncMock()
    mock_post_response.status_code = 200
    mock_post_response.json.return_value = {"id": "art1", "artifact_type": "specification"}
    
    with patch("httpx.AsyncClient.get", return_value=mock_get_response):
        with patch("httpx.AsyncClient.post", return_value=mock_post_response):
            result = await services.save_l2_artifact("test_project", {"title": "Test Project"})
            assert result["id"] == "art1"
            assert result["artifact_type"] == "specification"

@pytest.mark.asyncio
async def test_save_l2_artifact_already_exists():
    """Тест пропуска сохранения если L2 уже существует."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"artifact_type": "specification", "id": "existing"}
    ]
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await services.save_l2_artifact("test_project", {"title": "Test Project"})
        assert result["status"] == "skipped"
        assert "L2 already exists" in result["message"]

@pytest.mark.asyncio
async def test_finalize_l2_with_skill():
    """Тест формирования L2 через навык discovery."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "l2": {
                "title": "Test Project",
                "description": "Test description",
                "requirements": ["req1", "req2"],
                "technical_specs": {"stack": "Python"}
            }
        }
    }
    
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        messages = [{"role": "user", "content": "test"}]
        l2_data = await services.finalize_l2("test_project", messages)
        assert l2_data["title"] == "Test Project"
        assert "requirements" in l2_data

@pytest.mark.asyncio
async def test_finalize_l2_fallback():
    """Тест fallback формирования L2 через прямой вызов LLM."""
    mock_skill_response = AsyncMock()
    mock_skill_response.status_code = 500  # Ошибка навыка
    
    mock_llm_response = AsyncMock()
    mock_llm_response.status_code = 200
    mock_llm_response.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "title": "Fallback Project",
                    "description": "Fallback description",
                    "requirements": ["req1"],
                    "technical_specs": {}
                })
            }
        }]
    }
    
    with patch("httpx.AsyncClient.post", side_effect=[Exception("Skill error"), mock_llm_response]):
        messages = [{"role": "user", "content": "test"}]
        l2_data = await services.finalize_l2("test_project", messages)
        assert l2_data["title"] == "Fallback Project"

@pytest.mark.asyncio
async def test_process_dialog_force_l2_creation():
    """Тест принудительного создания L2 после 4 сообщений."""
    # Мокаем зависимости
    mock_ensure_project = AsyncMock(return_value=("proj1", "sess1", [], {}))
    mock_get_user_count = AsyncMock(return_value=4)  # 4 сообщения пользователя
    mock_get_history = AsyncMock(return_value=[
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "reply1"},
        {"role": "user", "content": "msg2"},
        {"role": "assistant", "content": "reply2"},
        {"role": "user", "content": "msg3"},
        {"role": "assistant", "content": "reply3"},
        {"role": "user", "content": "msg4"}
    ])
    mock_finalize_l2 = AsyncMock(return_value={
        "title": "Forced L2",
        "description": "Forced description",
        "requirements": ["req1", "req2"],
        "technical_specs": {"stack": "Python"}
    })
    mock_save_artifact = AsyncMock(return_value={"id": "art1"})
    mock_process_l2 = AsyncMock(return_value=(
        "✅ Проект сформирован, передан архитектору.",
        True,
        "task123",
        {"title": "Forced L2"}
    ))
    
    with patch("services._ensure_project_exists", mock_ensure_project):
        with patch("services.get_user_messages_count", mock_get_user_count):
            with patch("services.get_dialog_history", mock_get_history):
                with patch("services.finalize_l2", mock_finalize_l2):
                    with patch("services.save_l2_artifact", mock_save_artifact):
                        with patch("services._process_l2_response", mock_process_l2):
                            with patch("services._save_message", AsyncMock()):
                                with patch("services.send_log_to_br18", AsyncMock()):
                                    with patch("services.repo.save_session", MagicMock()):
                                        result = await services.process_dialog("proj1", "test message")
                                        
                                        # Проверяем, что функция вернула результат принудительного создания L2
                                        assert result[0] == "✅ Проект сформирован, передан архитектору."
                                        assert result[1] is True  # completed
                                        assert result[2] == "task123"  # task_id
                                        # Проверяем, что были вызваны нужные функции
                                        mock_get_user_count.assert_called_once_with("proj1")
                                        mock_finalize_l2.assert_called_once()
                                        mock_save_artifact.assert_called_once()
                                        mock_process_l2.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])