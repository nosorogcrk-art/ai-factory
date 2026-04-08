import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompt_analyzer import (
    fetch_dialog_history,
    call_dialog_analyzer_skill,
    send_to_prompt_optimizer,
    analyze_project_dialog
)

# Тестовые данные
TEST_MESSAGES = [
    {"role": "user", "content": "Привет, помоги мне создать систему"},
    {"role": "assistant", "content": "Конечно! Расскажите, что вам нужно?"},
    {"role": "user", "content": "Не понял, что ты имеешь в виду"},
    {"role": "assistant", "content": "Я имею в виду систему для управления задачами"},
    {"role": "user", "content": "ок"},
    {"role": "assistant", "content": "Хорошо, давайте начнём с требований"},
    {"role": "user", "content": "требования"},
    {"role": "assistant", "content": "Хорошо, давайте начнём с требований"},  # Повтор
]

TEST_PROJECT_ID = "proj_test_123"
TEST_SKILL_ID = "SKILL-DISCOVERY-001"

@pytest.mark.asyncio
async def test_fetch_dialog_history_success():
    """Тест успешного получения истории диалога."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"messages": TEST_MESSAGES}
    
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
        messages = await fetch_dialog_history(TEST_PROJECT_ID, limit=10)
        
        assert len(messages) == len(TEST_MESSAGES)
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Привет, помоги мне создать систему"

@pytest.mark.asyncio
async def test_fetch_dialog_history_failure():
    """Тест обработки ошибки при получении истории."""
    with patch("httpx.AsyncClient.get", AsyncMock(side_effect=Exception("Connection error"))):
        messages = await fetch_dialog_history(TEST_PROJECT_ID)
        assert messages == []

@pytest.mark.asyncio
async def test_call_dialog_analyzer_skill_success():
    """Тест успешного вызова навыка dialog_analyzer."""
    expected_result = {
        "analysis": "Краткий анализ диалога",
        "suggestions": ["предложение 1", "предложение 2"],
        "risk_level": "medium"
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": expected_result}
    
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)):
        result = await call_dialog_analyzer_skill(TEST_MESSAGES)
        assert result == expected_result

@pytest.mark.asyncio
async def test_call_dialog_analyzer_skill_failure():
    """Тест обработки ошибки при вызове навыка."""
    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=Exception("Connection error"))):
        result = await call_dialog_analyzer_skill(TEST_MESSAGES)
        assert result["analysis"] == "Не удалось получить анализ"
        assert result["suggestions"] == []
        assert result["risk_level"] == "unknown"

@pytest.mark.asyncio
async def test_call_dialog_analyzer_skill_invalid_json():
    """Тест обработки некорректного ответа от навыка."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}  # Нет поля result
    
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)):
        result = await call_dialog_analyzer_skill(TEST_MESSAGES)
        assert result["analysis"] == "Не удалось получить анализ"
        assert result["suggestions"] == []
        assert result["risk_level"] == "unknown"

@pytest.mark.asyncio
async def test_send_to_prompt_optimizer_success():
    """Тест успешной отправки предложений в оптимизатор."""
    suggestions = ["Улучшить промпт", "Добавить примеры"]
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)):
        success = await send_to_prompt_optimizer(TEST_SKILL_ID, suggestions)
        assert success is True

@pytest.mark.asyncio
async def test_send_to_prompt_optimizer_failure():
    """Тест обработки ошибки при отправке в оптимизатор."""
    suggestions = ["Улучшить промпт"]
    
    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=Exception("Connection failed"))):
        success = await send_to_prompt_optimizer(TEST_SKILL_ID, suggestions)
        assert success is False

@pytest.mark.asyncio
async def test_send_to_prompt_optimizer_empty_suggestions():
    """Тест отправки пустого списка предложений."""
    success = await send_to_prompt_optimizer(TEST_SKILL_ID, [])
    assert success is True

@pytest.mark.asyncio
async def test_analyze_project_dialog_success():
    """Тест успешного анализа диалога проекта."""
    skill_result = {
        "analysis": "Анализ диалога",
        "suggestions": ["Улучшить промпт", "Добавить примеры"],
        "risk_level": "medium"
    }
    
    # Мокаем fetch_dialog_history
    with patch("prompt_analyzer.fetch_dialog_history", AsyncMock(return_value=TEST_MESSAGES)):
        # Мокаем call_dialog_analyzer_skill
        with patch("prompt_analyzer.call_dialog_analyzer_skill", AsyncMock(return_value=skill_result)):
            # Мокаем send_to_prompt_optimizer
            with patch("prompt_analyzer.send_to_prompt_optimizer", AsyncMock(return_value=True)):
                # Мокаем сохранение файла
                with patch("builtins.open", MagicMock()) as mock_file:
                    mock_file.return_value.__enter__.return_value.write = MagicMock()
                    
                    result = await analyze_project_dialog(TEST_PROJECT_ID, TEST_SKILL_ID)
                    
                    assert "analysis" in result
                    assert result["analysis"] == "Анализ диалога"
                    assert result["suggestions"] == ["Улучшить промпт", "Добавить примеры"]
                    assert result["risk_level"] == "medium"

@pytest.mark.asyncio
async def test_analyze_project_dialog_no_messages():
    """Тест анализа проекта без сообщений."""
    with patch("prompt_analyzer.fetch_dialog_history", AsyncMock(return_value=[])):
        result = await analyze_project_dialog(TEST_PROJECT_ID, TEST_SKILL_ID)
        
        assert result["status"] == "no_messages"
        assert result["project_id"] == TEST_PROJECT_ID

@pytest.mark.asyncio
async def test_analyze_project_dialog_skill_failure():
    """Тест анализа проекта при ошибке навыка."""
    skill_result = {
        "analysis": "Не удалось получить анализ",
        "suggestions": [],
        "risk_level": "unknown"
    }
    
    with patch("prompt_analyzer.fetch_dialog_history", AsyncMock(return_value=TEST_MESSAGES)):
        with patch("prompt_analyzer.call_dialog_analyzer_skill", AsyncMock(return_value=skill_result)):
            with patch("builtins.open", MagicMock()) as mock_file:
                mock_file.return_value.__enter__.return_value.write = MagicMock()
                
                result = await analyze_project_dialog(TEST_PROJECT_ID, TEST_SKILL_ID)
                
                assert result["analysis"] == "Не удалось получить анализ"
                assert result["suggestions"] == []
                assert result["risk_level"] == "unknown"