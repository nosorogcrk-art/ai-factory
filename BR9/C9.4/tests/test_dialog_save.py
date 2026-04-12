import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_save_user_message_called():
    """Проверяем, что при вызове /api/dialog сохраняется сообщение пользователя."""
    with patch("services._ensure_project_exists", new=AsyncMock()) as mock_ensure:
        mock_ensure.return_value = ("test", "session_id", [], {})
        with patch("services.call_skill_integrator", new=AsyncMock()) as mock_skill:
            mock_skill.return_value = {"prompt": "test prompt", "skill_id": "discovery"}
            with patch("services._call_llm", new=AsyncMock()) as mock_llm:
                mock_llm.return_value = "Ответ ассистента"
                with patch("services._parse_l2_response", new=MagicMock()) as mock_parse:
                    mock_parse.return_value = (False, {})
                    with patch("repositories.save_session", new=MagicMock()):
                        with patch("services._save_message", new=AsyncMock()) as mock_save:
                            # Вызываем API
                            response = client.post("/api/dialog", json={"project_id": "test", "message": "Hello"})
                            # Проверяем, что сохранение вызвано с правильными аргументами
                            mock_save.assert_any_await("test", "user", "Hello")
                            # Также проверяем, что сохранение ассистента вызвано (если не было L2)
                            mock_save.assert_any_await("test", "assistant", "Ответ ассистента")
                            # Проверяем, что ответ API получен
                            assert response.status_code == 200


def test_dialog_flow_saves_both_messages():
    """Интеграционный тест: проверяем, что оба сообщения сохраняются."""
    # Мокаем внешние зависимости
    async def mock_save(project_id, role, content):
        pass
    async def mock_ensure(project_id, message):
        return project_id, "session_id", [], {}
    async def mock_skill(task_type):
        return {"prompt": "prompt", "skill_id": "discovery"}
    async def mock_llm(messages):
        return "Ответ ассистента"
    mock_parse = MagicMock(return_value=(False, {}))
    
    with patch("services._save_message", side_effect=mock_save) as mock_save_call:
        with patch("services._ensure_project_exists", side_effect=mock_ensure):
            with patch("services.call_skill_integrator", side_effect=mock_skill):
                with patch("services._call_llm", side_effect=mock_llm):
                    with patch("services._parse_l2_response", mock_parse):
                        with patch("repositories.save_session"):
                            response = client.post("/api/dialog", json={"project_id": "test", "message": "Hi"})
                            assert response.status_code == 200
                            # Проверяем, что сохранение вызывалось дважды
                            assert mock_save_call.call_count == 2
                            # Первый вызов - user
                            call_args_list = mock_save_call.call_args_list
                            assert call_args_list[0][0] == ("test", "user", "Hi")
                            assert call_args_list[1][0] == ("test", "assistant", "Ответ ассистента")
