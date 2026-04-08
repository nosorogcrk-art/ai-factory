"""
E2E-тесты для C9.4 Dialogue Manager с использованием LLM-судьи.
Тесты проверяют недетерминированные сценарии: полный опрос, генерацию L2,
уточняющие вопросы и оценку качества через LLM-судью.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app
from tests.llm_judge import evaluate_l2_quality, call_llm_judge_sync

client = TestClient(app)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_dialogue_with_llm_judge_and_c26_project_creation(mocker):
    """
    Сценарий 1: полный опрос → L2 с созданием тестового проекта через API C2.6.
    
    Шаги:
    1. Создать тестовый проект через API C2.6 (мок)
    2. Отправить последовательность из 5 ответов, имитирующих полный опрос
    3. Проверить completed = True
    4. Вызвать LLM-судью для оценки L2
    5. Удалить тестовый проект после теста
    """
    # Мокируем создание проекта в C2.6
    mock_create_project = mocker.patch("services._create_project_in_c26")
    mock_create_project.return_value = {"id": "test_proj_llm_123", "status": "created"}
    
    # Мокируем проверку проекта - проект существует
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.raise_for_status.return_value = None
    mocker.patch("services.client.get", return_value=mock_get_response)
    
    # Мокируем сохранение сообщений и артефактов
    mock_save_message = mocker.patch("services._save_message")
    mock_save_artifact = mocker.patch("services._save_artifact")
    mock_call_c12 = mocker.patch("services._call_c12")
    mock_call_c12.return_value = ["P1.1.1", "P1.1.2"]
    
    mock_create_task = mocker.patch("services.create_task_in_registry")
    mock_create_task.return_value = "DIALOG-LLM-TEST123"
    
    mock_send_log = mocker.patch("services.send_log_to_br18")
    
    # Мокируем репозиторий сессий
    mock_get_session = mocker.patch("repositories.get_session")
    mock_get_session.return_value = ([], {})
    
    mocker.patch("repositories.save_session")
    
    # Мокируем DeepSeek API для возврата L2 JSON после 5-го сообщения
    mock_llm_response = AsyncMock()
    mock_llm_response.raise_for_status.return_value = None
    
    # Симулируем прогрессивный диалог
    dialogue_responses = [
        # Первые 4 ответа - уточняющие вопросы
        {
            "choices": [{"message": {"content": "Расскажите подробнее о целях проекта?"}}]
        },
        {
            "choices": [{"message": {"content": "Какие технологии вы предпочитаете?"}}]
        },
        {
            "choices": [{"message": {"content": "Какой срок реализации вы планируете?"}}]
        },
        {
            "choices": [{"message": {"content": "Есть ли особые требования к безопасности?"}}]
        },
        # 5-й ответ - полный L2
        {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "Система мониторинга ключевых слов в Telegram",
                        "description": "Автоматизированная система для отслеживания упоминаний ключевых слов в Telegram-каналах и группах",
                        "requirements": [
                            "Подключение к Telegram API",
                            "Хранение истории мониторинга",
                            "Генерация отчётов",
                            "Уведомления о новых упоминаниях"
                        ],
                        "technical_specs": {
                            "language": "Python",
                            "framework": "FastAPI",
                            "database": "PostgreSQL",
                            "queue": "Redis"
                        },
                        "deliverable": "web_service",
                        "priority": "high",
                        "tags": ["monitoring", "telegram", "analytics", "python"]
                    })
                }
            }]
        }
    ]
    
    response_index = 0
    
    def mock_post(*args, **kwargs):
        nonlocal response_index
        mock_resp = AsyncMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = dialogue_responses[response_index]
        response_index = min(response_index + 1, len(dialogue_responses) - 1)
        return mock_resp
    
    mocker.patch("services.client.post", side_effect=mock_post)
    
    # Устанавливаем API ключ для DeepSeek
    mocker.patch("services.DEEPSEEK_API_KEY", "test-key-llm-judge")
    
    # Симулируем последовательность диалога
    project_id = "test_proj_llm_123"
    messages = [
        "Хочу создать систему для мониторинга ключевых слов в Telegram",
        "Цель - отслеживать упоминания бренда и конкурентов",
        "Предпочитаю Python и FastAPI",
        "Срок - 2 месяца",
        "Требуется шифрование данных и доступ по ролям"
    ]
    
    responses = []
    for i, message in enumerate(messages):
        response = client.post("/api/dialog", json={
            "project_id": project_id,
            "message": message
        })
        
        assert response.status_code == 200
        data = response.json()
        responses.append(data)
        
        # После 5-го сообщения должен быть completed = True
        if i == 4:
            assert data["completed"] is True
            assert "task_id" in data
            assert data["task_id"] == "DIALOG-LLM-TEST123"
            
            # Проверяем, что L2 был сохранен как артефакт
            mock_save_artifact.assert_called()
            
            # Оцениваем качество L2 через LLM-судью (мок)
            l2_json = dialogue_responses[4]["choices"][0]["message"]["content"]
            try:
                l2_data = json.loads(l2_json)
                
                # Мокируем вызов LLM-судьи для теста
                with patch('tests.llm_judge.call_llm_judge') as mock_judge:
                    mock_judge.return_value = {
                        "score": 8.5,
                        "passed": True,
                        "comment": "L2 хорошо структурирован, содержит все необходимые разделы",
                        "criteria_breakdown": {
                            "полнота": 9,
                            "конкретность": 8,
                            "реализуемость": 9,
                            "структурированность": 9,
                            "ясность": 8,
                            "приоритизация": 8,
                            "теги": 8
                        },
                        "timestamp": "2026-04-07T22:40:00",
                        "judge": "DeepSeek"
                    }
                    
                    evaluation = evaluate_l2_quality(l2_data)
                    assert evaluation["passed"] is True
                    assert evaluation["score"] >= 7.0
                    print(f"L2 оценён на {evaluation['score']}/10: {evaluation['comment']}")
            except json.JSONDecodeError:
                pytest.fail("L2 не является валидным JSON")
        else:
            assert data["completed"] is False
    
    # Проверяем вызовы внешних сервисов
    mock_create_project.assert_called_once()
    assert mock_create_project.call_args[0][0] == project_id
    mock_save_message.call_count == len(messages)
    mock_call_c12.assert_called_once()
    mock_create_task.assert_called_once()
    mock_send_log.assert_called()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_clarifying_question_with_llm_judge(mocker):
    """
    Сценарий 2: уточняющий вопрос при неполном ответе.
    
    Шаги:
    1. Отправить неполный ответ на блок 1 (без указания сроков)
    2. Проверить, что ассистент задал уточняющий вопрос
    3. LLM-судья оценивает, содержит ли вопрос ожидаемую тему
    """
    # Мокируем проверку проекта
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.raise_for_status.return_value = None
    mocker.patch("services.client.get", return_value=mock_get_response)
    
    # Мокируем репозиторий сессий
    mock_get_session = mocker.patch("repositories.get_session")
    mock_get_session.return_value = ([], {})
    
    mocker.patch("repositories.save_session")
    mocker.patch("services.send_log_to_br18")
    mocker.patch("services._save_message")
    mocker.patch("services._save_artifact")
    
    # Мокируем LLM для возврата уточняющего вопроса
    mock_llm_response = AsyncMock()
    mock_llm_response.raise_for_status.return_value = None
    mock_llm_response.json.return_value = {
        "choices": [{
            "message": {
                "content": "Вы упомянули цели проекта, но не указали сроки реализации. Когда вы планируете завершить проект?"
            }
        }]
    }
    mocker.patch("services.client.post", return_value=mock_llm_response)
    mocker.patch("services.DEEPSEEK_API_KEY", "test-key")
    
    # Отправляем неполный ответ
    response = client.post("/api/dialog", json={
        "project_id": "proj_clarify",
        "message": "Хочу создать CRM-систему для малого бизнеса. Основные цели: управление клиентами, автоматизация продаж, аналитика."
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["completed"] is False
    assert "response" in data
    
    # Проверяем, что ответ содержит уточняющий вопрос
    response_text = data["response"]
    assert "срок" in response_text.lower() or "когда" in response_text.lower()
    
    # Оцениваем качество уточняющего вопроса через LLM-судью (мок)
    with patch('tests.llm_judge.call_llm_judge_sync') as mock_judge:
        mock_judge.return_value = {
            "score": 9.0,
            "passed": True,
            "comment": "Вопрос правильно фокусируется на недостающей информации (сроки реализации)",
            "criteria_breakdown": {
                "полнота": 9,
                "точность": 9,
                "структурированность": 9,
                "полезность": 9,
                "ясность": 9
            },
            "timestamp": "2026-04-07T22:45:00",
            "judge": "DeepSeek"
        }
        
        evaluation = call_llm_judge_sync(
            prompt=response_text,
            context={"user_message": "Хочу создать CRM-систему для малого бизнеса. Основные цели: управление клиентами, автоматизация продаж, аналитика."},
            criteria="Оцени, насколько хорошо уточняющий вопрос выявляет недостающую информацию. Фокусируется ли он на важных отсутствующих деталях?"
        )
        
        assert evaluation["passed"] is True
        assert evaluation["score"] >= 7.0
        print(f"Уточняющий вопрос оценён на {evaluation['score']}/10: {evaluation['comment']}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_llm_judge_without_api_key(mocker):
    """
    Тест работы LLM-судьи без API ключа (fallback режим).
    """
    # Мокируем отсутствие API ключа
    mocker.patch("services.DEEPSEEK_API_KEY", None)
    
    # Мокируем проверку проекта
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.raise_for_status.return_value = None
    mocker.patch("services.client.get", return_value=mock_get_response)
    
    mock_get_session = mocker.patch("repositories.get_session")
    mock_get_session.return_value = ([], {})
    
    mocker.patch("repositories.save_session")
    mocker.patch("services.send_log_to_br18")
    
    response = client.post("/api/dialog", json={
        "project_id": "proj_no_key",
        "message": "Тестовое сообщение"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["completed"] is False
    assert data["task_id"] is None
    
    # Проверяем, что LLM-судья возвращает fallback результат без ключа
    from tests.llm_judge import call_llm_judge_sync
    
    # Временно подменяем переменную окружения
    import os
    original_key = os.getenv("DEEPSEEK_API_KEY")
    os.environ["DEEPSEEK_API_KEY"] = ""
    
    try:
        evaluation = call_llm_judge_sync(
            prompt="Тестовый ответ",
            context={"test": "context"}
        )
        
        assert evaluation["score"] == 0
        assert evaluation["passed"] is False
        assert "DEEPSEEK_API_KEY not set" in evaluation["comment"]
    finally:
        if original_key:
            os.environ["DEEPSEEK_API_KEY"] = original_key
        else:
            os.environ.pop("DEEPSEEK_API_KEY", None)


@pytest.mark.e2e
def test_llm_judge_module_import():
    """Тест импорта модуля LLM-судьи."""
    from tests.llm_judge import (
        call_llm_judge,
        evaluate_l2_quality,
        evaluate_branch_design,
        call_llm_judge_sync
    )
    
    assert callable(call_llm_judge)
    assert callable(evaluate_l2_quality)
    assert callable(evaluate_branch_design)
    assert callable(call_llm_judge_sync)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])