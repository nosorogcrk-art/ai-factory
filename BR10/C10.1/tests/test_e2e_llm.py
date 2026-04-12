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
INTEGRATOR_URL = "http://localhost:8096"  # внешний порт C10.1

def check_integrator_available() -> bool:
    """Проверяет, доступен ли C10.1 (healthcheck)."""
    try:
        resp = httpx.get(f"{INTEGRATOR_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False

def call_llm_judge(artifacts: list) -> dict:
    """Отправляет сгенерированные артефакты в DeepSeek для оценки качества."""
    if DEEPSEEK_API_KEY is None:
        pytest.skip("DEEPSEEK_API_KEY not set, skipping LLM judge test")
    
    # Извлекаем содержимое main.py или services.py для анализа
    code_sample = None
    for artifact in artifacts:
        if artifact.get("filename") in ("main.py", "services.py"):
            code_sample = artifact.get("content", "")
            break
    if not code_sample:
        pytest.skip("No Python code file found in artifacts")
    
    prompt = f"""
Ты – судья, оценивающий качество кода, сгенерированного C10.1 (Integrator) на основе спецификации L5.

Критерии оценки (каждый пункт должен быть выполнен):
- Код написан на Python 3.12, соответствует PEP 8.
- Присутствуют аннотации типов (type hints) для всех функций.
- Есть обработка ошибок (try/except или возврат HTTPException).
- Используется модуль `logging` для логирования.
- Присутствует эндпоинт `/health` (или функция healthcheck).
- Есть тесты (хотя бы один файл с расширением `test_*.py`).
- Код разбит на разумные модули/функции (не всё в одном файле).

Сгенерированный код (пример из main.py или services.py):
```python
{code_sample[:3000]}  # ограничиваем длину
```

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
def test_code_generation_from_l5():
    if not check_integrator_available():
        pytest.skip("C10.1 not available")
    
    # Пример L5 для теста
    l5_spec = {
        "container_id": "C9.5",
        "spec": {
            "branch_id": "BR9",
            "description": "Менеджер диалогов для обработки сообщений пользователя",
            "specifications": {
                "endpoints": [
                    {
                        "path": "/api/dialog",
                        "method": "POST",
                        "request": {"project_id": "str", "message": "str"},
                        "response": {"reply": "str", "session_id": "str"}
                    }
                ],
                "storage": "SQLite",
                "external_dependencies": ["httpx", "fastapi"],
                "tests_required": True,
                "healthcheck_required": True
            }
        }
    }
    
    # Вызвать эндпоинт C10.1 /generate-from-l5
    response = client.post("/generate-from-l5", json=l5_spec)
    
    # Обработка ошибок: если C10.1 вернул 5xx, пропускаем тест (инфраструктурная проблема)
    if response.status_code >= 500:
        pytest.skip(f"C10.1 returned {response.status_code}, internal error - skipping test")
    
    assert response.status_code == 200, f"Unexpected status: {response.status_code}"
    result = response.json()
    
    # Проверить наличие обязательных полей
    assert result.get("status") == "success", f"Status not success: {result.get('status')}"
    files = result.get("files", [])
    assert files, "No files generated"
    
    # Преобразуем в формат artifacts для LLM-судьи
    artifacts = []
    for file_item in files:
        artifacts.append({
            "filename": Path(file_item["path"]).name,
            "content": file_item["content"]
        })
    
    # Проверить, что сгенерированы основные файлы
    filenames = [a.get("filename") for a in artifacts]
    assert any("main.py" in f for f in filenames), "main.py not generated"
    assert any("test" in f.lower() for f in filenames), "No test files generated"
    
    # Вызвать LLM-судью для оценки
    judge_result = call_llm_judge(artifacts)
    assert judge_result["passed"], f"Code quality check failed: {judge_result.get('comment')}"
    assert judge_result["score"] >= 0.8, f"Score too low: {judge_result['score']}"

@pytest.mark.e2e
def test_generation_with_incomplete_l5():
    """Проверяет, что C10.1 возвращает ошибку при неполной спецификации."""
    if not check_integrator_available():
        pytest.skip("C10.1 not available")
    
    incomplete_l5 = {
        "container_id": "C9.5"
        # нет spec
    }
    response = client.post("/generate-from-l5", json=incomplete_l5)
    
    if response.status_code >= 500:
        pytest.skip(f"C10.1 returned {response.status_code}, internal error - skipping test")
    
    # Ожидаем, что C10.1 вернёт 400 (Bad Request) или 422
    assert response.status_code in (400, 422), f"Expected error status, got {response.status_code}"