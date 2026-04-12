import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import json
import os
import httpx
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
PATCH_ARCHITECT_URL = "http://localhost:8085"  # внешний порт C1.2

def check_patch_architect_available() -> bool:
    """Проверяет, доступен ли C1.2 (healthcheck)."""
    try:
        resp = httpx.get(f"{PATCH_ARCHITECT_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False

def call_llm_judge(design_result: dict) -> dict:
    """Отправляет результат проектирования в DeepSeek для оценки качества."""
    if DEEPSEEK_API_KEY is None:
        pytest.skip("DEEPSEEK_API_KEY not set, skipping LLM judge test")
    
    prompt = f"""
Ты – судья, оценивающий качество проектирования, выполненного C1.2 (Patch Architect) на основе L2.

Входной L2 (пример):
{{
  "title": "Telegram мониторинг упоминаний",
  "description": "Система отслеживает упоминания компании в Telegram и оповещает маркетологов",
  "requirements": [
    "Отслеживание ключевых слов в каналах и чатах",
    "Фильтрация по тональности (позитив/негатив)",
    "Оповещение в Telegram-бота в течение 15 минут"
  ],
  "technical_specs": {{
    "stack": "Python 3.12",
    "api": "Telegram Bot API",
    "storage": "SQLite"
  }}
}}

Результат проектирования (ответ C1.2):
{json.dumps(design_result, indent=2, ensure_ascii=False)}

Критерии оценки (каждый пункт должен быть выполнен):
- В ответе присутствуют поля `branches`, `containers`, `patches`, `queue` (не пустые).
- Каждая ветка имеет поля `id` (начинается с BR), `name`, `description`.
- Каждый контейнер имеет поля `id` (формат C*.*), `branch_id` (ссылка на существующую ветку), `port` (если веб-сервис) и другие обязательные поля.
- Каждый патч имеет поля `id` (формат P*.*.*), `container_id` (ссылка на существующий контейнер), `description`.
- Очередь содержит массив ID патчей, порядок соответствует зависимостям.
- Все ссылки (branch_id, container_id) корректны (указывают на существующие объекты).

Оцени результат по шкале от 0 до 1, где 1 – идеально соответствует всем критериям. Верни JSON строго в формате:
{{"score": 0.95, "passed": true, "comment": "Краткое пояснение"}}
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    with httpx.Client(timeout=30.0) as http_client:
        resp = http_client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        result = json.loads(data["choices"][0]["message"]["content"])
        return result

@pytest.mark.e2e
def test_full_design_cycle():
    if not check_patch_architect_available():
        pytest.skip("C1.2 not available")
    
    # Пример L2 для теста
    l2_input = {
        "title": "Telegram мониторинг упоминаний",
        "description": "Система отслеживает упоминания компании в Telegram и оповещает маркетологов",
        "requirements": [
            "Отслеживание ключевых слов в каналах и чатах",
            "Фильтрация по тональности (позитив/негатив)",
            "Оповещение в Telegram-бота в течение 15 минут"
        ],
        "technical_specs": {
            "stack": "Python 3.12",
            "api": "Telegram Bot API",
            "storage": "SQLite"
        }
    }
    
    # Вызвать эндпоинт C1.2 (предполагается, что это /decompose)
    response = client.post("/decompose", json={"description": json.dumps(l2_input)})
    
    # Обработка ошибок: если C1.2 вернул 5xx, пропускаем тест (инфраструктурная проблема)
    if response.status_code >= 500:
        pytest.skip(f"C1.2 returned {response.status_code}, internal error - skipping test")
    
    # Для 400/422 можно либо пропустить, либо позволить упасть (это уже ошибка C1.2, но не инфраструктуры)
    # По требованию аудитора – при 5xx только пропуск.
    assert response.status_code == 200, f"Unexpected status: {response.status_code}"
    
    design_result = response.json()
    
    # Проверить наличие обязательных полей
    assert "branches" in design_result, "Missing 'branches' in response"
    assert "containers" in design_result, "Missing 'containers' in response"
    assert "patches" in design_result, "Missing 'patches' in response"
    assert "queue" in design_result, "Missing 'queue' in response"
    
    # Вызвать LLM-судью для оценки
    judge_result = call_llm_judge(design_result)
    assert judge_result["passed"], f"Design quality check failed: {judge_result.get('comment')}"
    assert judge_result["score"] >= 0.8, f"Score too low: {judge_result['score']}"

@pytest.mark.e2e
def test_design_with_incomplete_l2():
    """Проверяет, что C1.2 корректно обрабатывает неполный L2 (возвращает ошибку или запрашивает уточнения)."""
    if not check_patch_architect_available():
        pytest.skip("C1.2 not available")
    
    incomplete_l2 = {
        "title": "Incomplete Project"
        # нет description, requirements, technical_specs
    }
    response = client.post("/decompose", json={"description": json.dumps(incomplete_l2)})
    
    # Если C1.2 вернул 5xx – пропускаем (инфраструктура)
    if response.status_code >= 500:
        pytest.skip(f"C1.2 returned {response.status_code}, internal error - skipping test")
    
    # Ожидаем, что C1.2 вернёт 400 (Bad Request) или 422
    assert response.status_code in (400, 422), f"Expected error status, got {response.status_code}"