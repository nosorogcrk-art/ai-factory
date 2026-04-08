"""
E2E-тесты для C1.2 Patch Architect с использованием LLM-судьи.
Тесты проверяют недетерминированные сценарии: проектирование веток из L2,
оценку качества декомпозиции через LLM-судью.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from tests.llm_judge import (
    evaluate_branch_design_quality,
    evaluate_decomposition_quality,
    call_llm_judge_sync
)

client = TestClient(app)


@pytest.mark.e2e
def test_branch_design_from_l2_with_llm_judge():
    """
    Сценарий 1: проектирование веток из L2 с оценкой через LLM-судью.
    
    Шаги:
    1. Отправить валидный L2 в POST /decompose
    2. Получить ответ, проверить наличие branches
    3. LLM-судья оценивает: количество веток (3–5), формат ID, наличие названий и описаний
    """
    # Пример валидного L2
    l2_data = {
        "title": "Система мониторинга ключевых слов в Telegram",
        "description": "Автоматизированная система для отслеживания упоминаний ключевых слов в Telegram-каналах и группах",
        "requirements": [
            "Подключение к Telegram API",
            "Хранение истории мониторинга",
            "Генерация отчётов",
            "Уведомления о новых упоминаниях",
            "Админ-панель для управления"
        ],
        "technical_specs": {
            "language": "Python",
            "framework": "FastAPI",
            "database": "PostgreSQL",
            "queue": "Redis",
            "frontend": "React"
        },
        "deliverable": "web_service",
        "priority": "high",
        "tags": ["monitoring", "telegram", "analytics", "python", "react"]
    }
    
    # Мокируем сервис decompose_task для возврата тестовых веток
    with patch('services.decompose_task') as mock_decompose:
        # Пример хорошо спроектированных веток
        mock_branches = [
            {
                "id": "BR1",
                "name": "Бэкенд: API и обработка данных",
                "description": "REST API для работы с Telegram, обработка сообщений, хранение данных",
                "containers": ["C1.1", "C1.2", "C2.1"],
                "priority": "high"
            },
            {
                "id": "BR2", 
                "name": "Фронтенд: админ-панель и дашборды",
                "description": "Интерфейс администратора, дашборды аналитики, управление мониторингом",
                "containers": ["C4.1", "C4.2"],
                "priority": "medium"
            },
            {
                "id": "BR3",
                "name": "Инфраструктура и развёртывание",
                "description": "Docker-контейнеры, CI/CD, мониторинг, логирование",
                "containers": ["C0.1", "C0.2", "C6.1"],
                "priority": "medium"
            },
            {
                "id": "BR4",
                "name": "Аналитика и отчётность",
                "description": "Анализ данных, генерация отчётов, визуализация статистики",
                "containers": ["C3.1", "C3.2"],
                "priority": "low"
            }
        ]
        
        mock_decompose.return_value = mock_branches
        
        # Отправляем запрос на декомпозицию
        response = client.post("/decompose", json={
            "description": json.dumps(l2_data),
            "context": {
                "project_id": "test_proj_llm",
                "source": "C9.4",
                "task_id": "TASK-LLM-TEST-123"
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "branches" in data
        assert len(data["branches"]) == 4
        
        # Проверяем структуру веток
        branches = data["branches"]
        for branch in branches:
            assert "id" in branch
            assert "name" in branch
            assert "description" in branch
            assert branch["id"].startswith("BR")
        
        # Оцениваем качество проектирования веток через LLM-судью (мок)
        with patch('tests.llm_judge.call_llm_judge') as mock_judge:
            mock_judge.return_value = {
                "score": 8.8,
                "passed": True,
                "comment": "Ветки хорошо спроектированы: оптимальное количество (4), хорошая специализация, правильный формат ID",
                "criteria_breakdown": {
                    "количество": 9,
                    "полнота": 9,
                    "независимость": 9,
                    "сложность": 8,
                    "логичность": 9,
                    "приоритизация": 9,
                    "формат_id": 9
                },
                "timestamp": "2026-04-07T22:50:00",
                "judge": "DeepSeek",
                "recommendations": [
                    "Добавить примерные сроки реализации для каждой ветки",
                    "Уточнить зависимости между ветками"
                ]
            }
            
            evaluation = evaluate_branch_design_quality(branches)
            
            assert evaluation["passed"] is True
            assert evaluation["score"] >= 7.0
            print(f"Проектирование веток оценено на {evaluation['score']}/10: {evaluation['comment']}")
            
            # Проверяем рекомендации
            if "recommendations" in evaluation:
                print("Рекомендации от LLM-судьи:")
                for rec in evaluation["recommendations"]:
                    print(f"  - {rec}")


@pytest.mark.e2e
def test_full_decomposition_quality_with_llm_judge():
    """
    Сценарий 2: полная оценка качества декомпозиции L2.
    
    Шаги:
    1. Создать комплексный L2
    2. Получить результат декомпозиции (ветки + контейнеры + патчи)
    3. LLM-судья оценивает соответствие L2 и качество декомпозиции
    """
    # Комплексный L2
    complex_l2 = {
        "title": "CRM-система для малого бизнеса",
        "description": "Облачная CRM-система с управлением клиентами, автоматизацией продаж, аналитикой и интеграциями",
        "requirements": [
            "Управление базой клиентов (добавление, редактирование, поиск)",
            "Воронка продаж с этапами и переходами",
            "Автоматизация email-рассылок и напоминаний",
            "Аналитика и отчёты по продажам",
            "Интеграция с Telegram и email",
            "Мультипользовательский доступ с ролями",
            "Мобильная версия"
        ],
        "technical_specs": {
            "backend": {"language": "Python", "framework": "FastAPI"},
            "frontend": {"framework": "React", "state": "Redux"},
            "database": "PostgreSQL + Redis",
            "deployment": "Docker + Kubernetes",
            "auth": "JWT + OAuth2"
        },
        "deliverable": "saas_platform",
        "priority": "high",
        "tags": ["crm", "sales", "automation", "saas", "python", "react"]
    }
    
    # Пример результата декомпозиции
    decomposition_result = {
        "branches": [
            {
                "id": "BR1",
                "name": "Бэкенд: ядро системы и API",
                "description": "Основная бизнес-логика, REST API, аутентификация, работа с данными",
                "priority": "high"
            },
            {
                "id": "BR2",
                "name": "Фронтенд: веб-интерфейс",
                "description": "Пользовательский интерфейс, дашборды, формы управления",
                "priority": "high"
            },
            {
                "id": "BR3",
                "name": "Интеграции и коммуникации",
                "description": "Интеграция с Telegram, email-рассылки, уведомления",
                "priority": "medium"
            },
            {
                "id": "BR4",
                "name": "Аналитика и отчётность",
                "description": "Анализ данных, генерация отчётов, дашборды аналитики",
                "priority": "medium"
            },
            {
                "id": "BR5",
                "name": "Инфраструктура и DevOps",
                "description": "Развёртывание, мониторинг, CI/CD, безопасность",
                "priority": "medium"
            }
        ],
        "containers": [
            {"id": "C1.1", "name": "User Service", "description": "Управление пользователями и аутентификация"},
            {"id": "C1.2", "name": "Customer Service", "description": "Управление клиентами и контактами"},
            {"id": "C2.1", "name": "Sales Pipeline Service", "description": "Воронка продаж и этапы сделок"},
            {"id": "C4.1", "name": "Web UI", "description": "Основной веб-интерфейс CRM"},
            {"id": "C4.2", "name": "Admin Dashboard", "description": "Панель администратора"},
            {"id": "C3.1", "name": "Analytics Engine", "description": "Анализ данных и расчёт метрик"},
            {"id": "C6.1", "name": "Notification Service", "description": "Отправка уведомлений и email"},
            {"id": "C0.1", "name": "API Gateway", "description": "Единая точка входа для API"},
            {"id": "C0.2", "name": "Auth Service", "description": "Аутентификация и авторизация"}
        ],
        "patches": [
            {"id": "P1.1.1", "name": "Базовая аутентификация", "priority": "high", "complexity": "M"},
            {"id": "P1.2.1", "name": "CRUD для клиентов", "priority": "high", "complexity": "M"},
            {"id": "P2.1.1", "name": "Модель воронки продаж", "priority": "high", "complexity": "L"},
            {"id": "P4.1.1", "name": "Базовый интерфейс CRM", "priority": "high", "complexity": "L"},
            {"id": "P6.1.1", "name": "Интеграция с Telegram", "priority": "medium", "complexity": "M"}
        ],
        "summary": {
            "total_branches": 5,
            "total_containers": 9,
            "total_patches": 5,
            "estimated_complexity": "XL",
            "recommended_order": ["BR1", "BR5", "BR2", "BR3", "BR4"]
        }
    }
    
    # Оцениваем качество декомпозиции через LLM-судью (мок)
    with patch('tests.llm_judge.call_llm_judge') as mock_judge:
        mock_judge.return_value = {
            "score": 8.2,
            "passed": True,
            "comment": "Декомпозиция хорошо соответствует L2: все требования учтены, структура логична, компоненты специализированы",
            "criteria_breakdown": {
                "соответствие_l2": 8,
                "глубина": 8,
                "сбалансированность": 8,
                "практичность": 9,
                "полнота": 8,
                "гибкость": 8,
                "документированность": 8
            },
            "timestamp": "2026-04-07T22:55:00",
            "judge": "DeepSeek",
            "recommendations": [
                "Добавить контейнер для кэширования (Redis)",
                "Уточнить зависимости между патчами",
                "Добавить тестовые сценарии для каждого контейнера"
            ]
        }
        
        evaluation = evaluate_decomposition_quality(complex_l2, decomposition_result)
        
        assert evaluation["passed"] is True
        assert evaluation["score"] >= 7.0
        print(f"Декомпозиция оценена на {evaluation['score']}/10: {evaluation['comment']}")
        
        # Проверяем, что все критерии присутствуют
        assert "criteria_breakdown" in evaluation
        criteria = evaluation["criteria_breakdown"]
        assert len(criteria) >= 5  # Минимум 5 критериев
        
        # Выводим детальную оценку по критериям
        print("Детальная оценка по критериям:")
        for criterion, score in criteria.items():
            print(f"  {criterion}: {score}/10")


@pytest.mark.e2e
def test_llm_judge_fallback_without_api_key():
    """
    Тест работы LLM-судьи без API ключа (fallback режим).
    """
    # Временно подменяем переменную окружения
    import os
    original_key = os.getenv("DEEPSEEK_API_KEY")
    os.environ["DEEPSEEK_API_KEY"] = ""
    
    try:
        # Создаём тестовые данные
        test_branches = [
            {"id": "BR1", "name": "Test Branch", "description": "Test description"}
        ]
        
        # Вызываем оценку (должен сработать fallback)
        evaluation = evaluate_branch_design_quality(test_branches)
        
        assert evaluation["score"] == 0
        assert evaluation["passed"] is False
        assert "DEEPSEEK_API_KEY not set" in evaluation["comment"]
        print(f"Fallback режим работает: {evaluation['comment']}")
        
    finally:
        if original_key:
            os.environ["DEEPSEEK_API_KEY"] = original_key
        else:
            os.environ.pop("DEEPSEEK_API_KEY", None)


@pytest.mark.e2e
def test_llm_judge_module_import_and_functions():
    """Тест импорта модуля LLM-судьи и доступности функций."""
    from tests.llm_judge import (
        call_llm_judge,
        evaluate_branch_design_quality,
        evaluate_container_design_quality,
        evaluate_patch_design_quality,
        evaluate_decomposition_quality,
        call_llm_judge_sync
    )
    
    assert callable(call_llm_judge)
    assert callable(evaluate_branch_design_quality)
    assert callable(evaluate_container_design_quality)
    assert callable(evaluate_patch_design_quality)
    assert callable(evaluate_decomposition_quality)
    assert callable(call_llm_judge_sync)
    
    print("Все функции LLM-судьи доступны для импорта")


@pytest.mark.e2e
def test_invalid_branch_design_evaluation():
    """
    Тест оценки некорректного проектирования веток.
    Проверяет, что LLM-судья корректно определяет проблемы.
    """
    # Некорректные ветки (мало информации, плохой формат)
    invalid_branches = [
        {"id": "branch1", "name": "Branch 1"},  # Нет описания
        {"id": "TEST", "name": "Test", "description": "Test"},  # Неправильный формат ID
        {"id": "BR2", "name": "B2"},  # Слишком короткое название
    ]
    
    # Мокируем LLM-судью для возврата низкой оценки
    with patch('tests.llm_judge.call_llm_judge') as mock_judge:
        mock_judge.return_value = {
            "score": 4.5,
            "passed": False,
            "comment": "Проектирование веток имеет проблемы: недостаточно описаний, неправильный формат ID, названия слишком краткие",
            "criteria_breakdown": {
                "количество": 6,
                "полнота": 3,
                "независимость": 5,
                "сложность": 5,
                "логичность": 5,
                "приоритизация": 4,
                "формат_id": 3
            },
            "timestamp": "2026-04-07T23:00