"""
Тесты для двухэтапного процесса генерации L2:
1. Опрос через discovery (без JSON)
2. Генерация L2 через l2_extractor после 4 сообщений
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import process_dialog, call_l2_extractor
from llm_client import _parse_l2_response


@pytest.mark.asyncio
async def test_discovery_does_not_return_json():
    """Проверка, что discovery возвращает текст, а не JSON."""
    # Мокаем внешние зависимости
    with patch("handlers._ensure_project_exists") as mock_ensure, \
         patch("services.get_user_messages_count") as mock_count, \
         patch("services.call_skill_integrator") as mock_skill, \
         patch("services._call_llm") as mock_llm, \
         patch("services._save_message") as mock_save, \
         patch("services.send_log_to_br18") as mock_log:
        
        # Настраиваем моки
        mock_ensure.return_value = ("test-project", "session-id", [], {})
        mock_count.return_value = 0  # Меньше 4 сообщений
        mock_skill.return_value = {"prompt": "test prompt", "skill_id": "discovery"}
        
        # Имитируем текстовый ответ от discovery (не JSON)
        mock_llm.return_value = "Какую главную проблему решает проект?"
        
        # Вызываем process_dialog
        reply, completed, task_id, task_desc = await process_dialog(
            "test-project", "Хочу создать парсер Telegram"
        )
        
        # Проверяем, что ответ не JSON
        assert not completed
        assert task_id is None
        assert "Какую главную проблему" in reply or "RAW" in reply
        
        # Проверяем, что _parse_l2_response возвращает False для этого ответа
        is_l2, l2_data = _parse_l2_response(mock_llm.return_value)
        assert not is_l2
        assert l2_data is None


@pytest.mark.asyncio
async def test_l2_extractor_called_after_4_messages():
    """Проверка, что после 4 сообщений вызывается l2_extractor."""
    with patch("handlers._ensure_project_exists") as mock_ensure, \
         patch("services.get_user_messages_count") as mock_count, \
         patch("services.get_dialog_history") as mock_history, \
         patch("services.call_l2_extractor") as mock_l2_extractor, \
         patch("services.save_l2_artifact") as mock_save_artifact, \
         patch("handlers._process_l2_response") as mock_process, \
         patch("services._save_message") as mock_save, \
         patch("services.send_log_to_br18") as mock_log, \
         patch("services.repo.save_session") as mock_repo_save:
        
        # Настраиваем моки
        mock_ensure.return_value = ("test-project", "session-id", [], {})
        mock_count.return_value = 4  # Ровно 4 сообщения
        mock_history.return_value = [
            {"role": "user", "content": "Сообщение 1"},
            {"role": "assistant", "content": "Ответ 1"},
            {"role": "user", "content": "Сообщение 2"},
            {"role": "assistant", "content": "Ответ 2"},
            {"role": "user", "content": "Сообщение 3"},
            {"role": "assistant", "content": "Ответ 3"},
            {"role": "user", "content": "Сообщение 4"},
        ]
        
        # Имитируем успешный вызов l2_extractor
        mock_l2_data = {
            "title": "Test Project",
            "description": "Test description",
            "requirements": ["Requirement 1", "Requirement 2"],
            "technical_specs": {"languages": ["Python"], "frameworks": []}
        }
        mock_l2_extractor.return_value = mock_l2_data
        mock_save_artifact.return_value = {"status": "created"}
        mock_process.return_value = ("✅ Проект сформирован", True, "task-123", mock_l2_data)
        
        # Вызываем process_dialog
        reply, completed, task_id, task_desc = await process_dialog(
            "test-project", "Четвёртое сообщение"
        )
        
        # Проверяем, что l2_extractor был вызван
        mock_l2_extractor.assert_called_once()
        
        # Проверяем, что save_l2_artifact был вызван
        mock_save_artifact.assert_called_once_with("test-project", mock_l2_data)
        
        # Проверяем, что процесс завершился успешно
        assert completed is True
        assert task_id == "task-123"
        assert "✅" in reply


@pytest.mark.asyncio
async def test_l2_extractor_fallback_to_llm():
    """Проверка fallback на прямой вызов LLM при ошибке l2_extractor."""
    with patch("handlers._ensure_project_exists") as mock_ensure, \
         patch("services.get_user_messages_count") as mock_count, \
         patch("services.get_dialog_history") as mock_history, \
         patch("services.call_l2_extractor") as mock_l2_extractor, \
         patch("services.generate_l2_via_llm") as mock_fallback, \
         patch("services.save_l2_artifact") as mock_save_artifact, \
         patch("handlers._process_l2_response") as mock_process, \
         patch("services._save_message") as mock_save, \
         patch("services.send_log_to_br18") as mock_log:
        
        # Настраиваем моки
        mock_ensure.return_value = ("test-project", "session-id", [], {})
        mock_count.return_value = 4
        mock_history.return_value = [{"role": "user", "content": "test"}]
        
        # Имитируем ошибку l2_extractor
        mock_l2_extractor.side_effect = Exception("Skill failed")
        
        # Имитируем успешный fallback
        mock_l2_data = {
            "title": "Fallback Project",
            "description": "Fallback description",
            "requirements": ["Req 1"],
            "technical_specs": {}
        }
        mock_fallback.return_value = mock_l2_data
        mock_save_artifact.return_value = {"status": "created"}
        mock_process.return_value = ("✅ Проект сформирован", True, "task-456", mock_l2_data)
        
        # Вызываем process_dialog
        reply, completed, task_id, task_desc = await process_dialog(
            "test-project", "Сообщение"
        )
        
        # Проверяем, что fallback был вызван
        mock_fallback.assert_called_once()
        
        # Проверяем, что процесс завершился успешно
        assert completed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])